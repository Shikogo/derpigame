"""An async Derpibooru client: random images and tag-alias resolution.

Fetches a random image matching a room's query, and resolves a guessed alias to
its canonical tag — both straight from Derpibooru's REST API with ``httpx``, no
blocking calls inside the event loop.

Image search and tag lookup live on one client on purpose: they must share the
back-off state, because Derpibooru's mandatory back-offs are per-IP and apply to
every endpoint. A cooldown gate refuses to touch the network while we owe a
back-off — a 501 anti-bot challenge means stay silent ≥5s; a 500 means we're
IP-blocked ≥15min and *any* request during the block resets that timer.

Alias resolution is best-effort: on failure or during a back-off it returns the
guess unchanged (play degrades to literal matching), never raising. Resolved
aliases are cached process-wide, including every sibling alias the lookup reveals.
"""

import asyncio
import logging
import time
import urllib.parse
from collections import OrderedDict

import httpx

from app.config import DerpibooruSettings
from app.domain.rating import DERPIBOORU_AXES, RatingAxis
from app.service.image_source import Image, ImageSource, ImageSourceError, SearchOptions
from app.service.tag_resolver import TagResolver

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://derpibooru.org/api/v1/json/search/images"
_TAGS_URL = "https://derpibooru.org/api/v1/json/search/tags"
# Videos have no still representation — every size is a .webm — so the viewer has
# nothing to show. Excluded by mime type, not the "webm" tag: a few dozen uploads
# carry the mime type without the tag. webm is currently the only video type.
_EXCLUDE_VIDEO = "-mime_type:video/webm"

# Reverse of Derpibooru's tag-name → slug escaping, applied after url-decoding
# (which turns the "+" space escape back into a space). Order mirrors the reverse
# of how the site encodes, so a token can't be re-clobbered.
_SLUG_ESCAPES = [
    ("-plus-", "+"),
    ("-dot-", "."),
    ("-colon-", ":"),
    ("-bwslash-", "\\"),
    ("-fwslash-", "/"),
    ("-dash-", "-"),
]


class DerpibooruClient(ImageSource, TagResolver):
    @property
    def rating_axes(self) -> tuple[RatingAxis, ...]:
        return DERPIBOORU_AXES

    def __init__(
        self,
        *,
        config: DerpibooruSettings | None = None,
        client: httpx.AsyncClient | None = None,
        clock=time.monotonic,
        sleep=asyncio.sleep,
    ):
        self._config = config or DerpibooruSettings()
        self._client = client  # an injected client is reused (and owned) by the caller
        self._clock = clock
        self._sleep = sleep
        self._cooldown_until = 0.0
        self._failure_backoff = 0.0
        # guess/alias -> canonical, process-wide, bounded LRU (evicts past the cap).
        self._alias_cache: OrderedDict[str, str] = OrderedDict()
        # Request spacing: never send faster than window / limit, serialized so
        # concurrent bursts (several rooms configuring at once) can't both read a
        # stale slot. Only requests we actually send advance the cursor.
        self._min_interval = self._config.search_rate_window / self._config.search_rate_limit
        self._next_slot = 0.0
        self._request_lock = asyncio.Lock()

    async def random_image(self, query: list[str], *, options: SearchOptions) -> Image | None:
        self._guard_cooldown()  # refuse to hit the network while we owe a back-off

        terms = list(query) or ["*"]
        params: dict[str, str | int] = {
            "q": ",".join([*terms, _EXCLUDE_VIDEO, *self._filter_terms(options)]),
            "sf": "random",
            "per_page": 1,
            "filter_id": (
                self._config.nsfw_filter_id if options.nsfw else self._config.default_filter_id
            ),
        }
        if self._config.api_key:
            params["key"] = self._config.api_key

        payload = await self._get(_SEARCH_URL, params)
        images = payload.get("images") or []
        if not images:
            return None
        return _to_image(images[0])

    async def canonicalize(self, tag: str) -> str:
        """Resolve ``tag`` to its canonical name, or return it unchanged.

        Best-effort: a lookup that can't be made (back-off, network error) returns
        the tag as-is so guessing still works, just without alias leniency.
        """
        key = tag.strip().lower()
        if key in self._alias_cache:
            self._alias_cache.move_to_end(key)  # mark as recently used
            return self._alias_cache[key]

        params = {"q": f"aliases:{key}", "per_page": 1}
        if self._config.api_key:
            params["key"] = self._config.api_key
        try:
            self._guard_cooldown()  # don't resolve while we owe the server a back-off
            payload = await self._get(_TAGS_URL, params)
        except ImageSourceError as exc:
            logger.warning("Alias lookup for %r failed (%s); using literal match", key, exc)
            return key  # degrade to literal matching; don't poison the cache

        tags = payload.get("tags") or []
        if not tags:
            self._remember(key, key)  # no alias: cache the miss so we don't re-ask
            return key

        canonical = (tags[0].get("name") or key).lower()
        self._cache_alias_family(tags[0], canonical)
        self._remember(key, canonical)  # the queried form maps too, always
        return canonical

    def _cache_alias_family(self, tag: dict, canonical: str) -> None:
        """Cache the canonical tag and every sibling alias the lookup revealed."""
        self._remember(canonical, canonical)  # the canonical resolves to itself
        for alias in tag.get("aliases") or []:
            self._remember(_slug_to_name(alias), canonical)

    def _remember(self, key: str, canonical: str) -> None:
        """Cache one mapping as most-recently-used, evicting the LRU past the cap."""
        self._alias_cache[key] = canonical
        self._alias_cache.move_to_end(key)
        while len(self._alias_cache) > self._config.alias_cache_max:
            self._alias_cache.popitem(last=False)

    def _filter_terms(self, options: SearchOptions) -> list[str]:
        """The room's non-tag search terms; a setting that's off emits nothing."""
        terms = []
        if options.min_tag_count is not None:
            terms.append(f"tag_count.gte:{options.min_tag_count}")
        if options.min_score is not None:
            terms.append(f"score.gte:{options.min_score}")
        for axis in self.rating_axes:
            terms += [f"-{tag}" for tag in axis.excluded(options.rating_caps.get(axis.key))]
        return terms

    def _guard_cooldown(self) -> None:
        remaining = self._cooldown_until - self._clock()
        if remaining > 0:
            raise ImageSourceError(f"backing off from Derpibooru for {remaining:.0f}s")

    async def _space_requests(self) -> None:
        """Reserve the next request slot, sleeping if we'd otherwise send too soon.

        Runs after ``_guard_cooldown``, so a call refused during a back-off never
        reaches here and never consumes a slot — the cursor only advances for
        requests we go on to send.
        """
        async with self._request_lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            if slot > now:
                await self._sleep(slot - now)
            self._next_slot = slot + self._min_interval

    async def _get(self, url: str, params: dict) -> dict:
        await self._space_requests()  # stay under the search-path rate limit
        headers = {"User-Agent": self._config.user_agent}
        try:
            response = await self._request(url, params, headers)
        except httpx.HTTPError as exc:  # transport error / timeout
            self._back_off_failure()
            logger.warning(
                "Derpibooru request failed (%s); backing off %.1fs", exc, self._failure_backoff
            )
            raise ImageSourceError(str(exc)) from exc

        status = response.status_code
        if status == 501:  # anti-bot challenge (text/html body)
            self._cooldown(self._config.challenge_backoff)
            logger.warning(
                "Derpibooru anti-bot challenge (501); backing off %.0fs",
                self._config.challenge_backoff,
            )
            raise ImageSourceError(
                f"Derpibooru anti-bot challenge (501); backing off "
                f"{self._config.challenge_backoff:.0f}s"
            )
        if status == 500:  # IP blocked; sending again resets the timer
            self._cooldown(self._config.block_backoff)
            logger.error(
                "Derpibooru IP block (500); backing off %.0fmin", self._config.block_backoff / 60
            )
            raise ImageSourceError(
                f"Derpibooru block (500); backing off {self._config.block_backoff / 60:.0f}min"
            )
        if status >= 400:
            self._back_off_failure()
            logger.warning(
                "Derpibooru returned HTTP %d; backing off %.1fs", status, self._failure_backoff
            )
            raise ImageSourceError(f"Derpibooru returned HTTP {status}")

        try:
            payload = response.json()
        except ValueError as exc:
            self._back_off_failure()
            logger.warning(
                "Derpibooru returned invalid JSON; backing off %.1fs", self._failure_backoff
            )
            raise ImageSourceError("invalid JSON from Derpibooru") from exc

        self._failure_backoff = 0.0  # a good response clears the exponential back-off
        return payload

    async def _request(self, url: str, params: dict, headers: dict) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(url, params=params, headers=headers)
        async with httpx.AsyncClient(timeout=self._config.timeout) as client:
            return await client.get(url, params=params, headers=headers)

    def _cooldown(self, seconds: float) -> None:
        self._cooldown_until = self._clock() + seconds

    def _back_off_failure(self) -> None:
        self._failure_backoff = min(
            max(self._failure_backoff * 2, self._config.failure_backoff_base),
            self._config.failure_backoff_max,
        )
        self._cooldown(self._failure_backoff)


def _slug_to_name(slug: str) -> str:
    """Decode a Derpibooru tag slug back to its plain, lowercased tag name."""
    name = urllib.parse.unquote_plus(slug)  # "+" space escape and any %xx
    for token, char in _SLUG_ESCAPES:
        name = name.replace(token, char)
    return name.lower()


def _https(url: str) -> str:
    """Force a protocol-relative ``//host/…`` URL to https, per the API license."""
    return "https:" + url if url.startswith("//") else url


def _to_image(raw: dict) -> Image:
    reps = raw.get("representations") or {}
    image_id = str(raw.get("id", ""))
    return Image(
        id=image_id,
        tags=list(raw.get("tags") or []),
        thumb_url=_https(reps.get("medium", "")),
        full_url=_https(reps.get("full", "")),
        page_url=f"https://derpibooru.org/images/{image_id}" if image_id else "",
        source_url=raw.get("source_url") or None,
    )
