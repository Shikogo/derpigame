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

import time
import urllib.parse

import httpx

from app.service.image_source import Image, ImageSource, ImageSourceError
from app.service.tag_resolver import TagResolver

_SEARCH_URL = "https://derpibooru.org/api/v1/json/search/images"
_TAGS_URL = "https://derpibooru.org/api/v1/json/search/tags"
_USER_AGENT = "derpigame/0.1 (https://github.com/Shikogo/derpigame)"
# Derpibooru system filter that shows everything, incl. explicit — used for nsfw
# rooms. Sfw rooms send no filter and get the site default (hides explicit).
_EVERYTHING_FILTER_ID = "56027"

# Back-off durations (seconds) per Derpibooru's API rules.
_CHALLENGE_BACKOFF = 5.0  # 501 text/html anti-bot challenge: silence ≥5s
_BLOCK_BACKOFF = 15 * 60.0  # 500 empty body: IP blocked ≥15min; a request resets it
_FAILURE_BACKOFF_BASE = 1.0  # other failures back off exponentially from here...
_FAILURE_BACKOFF_MAX = 60.0  # ...capped here

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
    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
        clock=time.monotonic,
    ):
        self._api_key = api_key
        self._timeout = timeout
        self._client = client  # an injected client is reused (and owned) by the caller
        self._clock = clock
        self._cooldown_until = 0.0
        self._failure_backoff = 0.0
        self._alias_cache: dict[str, str] = {}  # guess/alias -> canonical, process-wide

    async def random_image(self, query: list[str], *, nsfw: bool) -> Image | None:
        self._guard_cooldown()  # refuse to hit the network while we owe a back-off

        params: dict[str, str | int] = {
            "q": ",".join(query) if query else "*",
            "sf": "random",
            "per_page": 1,
        }
        if nsfw:
            params["filter_id"] = _EVERYTHING_FILTER_ID
        if self._api_key:
            params["key"] = self._api_key

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
            return self._alias_cache[key]

        params = {"q": f"aliases:{key}", "per_page": 1}
        if self._api_key:
            params["key"] = self._api_key
        try:
            self._guard_cooldown()  # don't resolve while we owe the server a back-off
            payload = await self._get(_TAGS_URL, params)
        except ImageSourceError:
            return key  # degrade to literal matching; don't poison the cache

        tags = payload.get("tags") or []
        if not tags:
            self._alias_cache[key] = key  # no alias: cache the miss so we don't re-ask
            return key

        canonical = (tags[0].get("name") or key).lower()
        self._cache_alias_family(tags[0], canonical)
        self._alias_cache[key] = canonical  # the queried form maps too, always
        return canonical

    def _cache_alias_family(self, tag: dict, canonical: str) -> None:
        """Cache the canonical tag and every sibling alias the lookup revealed."""
        self._alias_cache[canonical] = canonical  # the canonical resolves to itself
        for alias in tag.get("aliases") or []:
            self._alias_cache[_slug_to_name(alias)] = canonical

    def _guard_cooldown(self) -> None:
        remaining = self._cooldown_until - self._clock()
        if remaining > 0:
            raise ImageSourceError(f"backing off from Derpibooru for {remaining:.0f}s")

    async def _get(self, url: str, params: dict) -> dict:
        headers = {"User-Agent": _USER_AGENT}
        try:
            response = await self._request(url, params, headers)
        except httpx.HTTPError as exc:  # transport error / timeout
            self._back_off_failure()
            raise ImageSourceError(str(exc)) from exc

        status = response.status_code
        if status == 501:  # anti-bot challenge (text/html body)
            self._cooldown(_CHALLENGE_BACKOFF)
            raise ImageSourceError("Derpibooru anti-bot challenge (501); backing off 5s")
        if status == 500:  # IP blocked; sending again resets the 15min timer
            self._cooldown(_BLOCK_BACKOFF)
            raise ImageSourceError("Derpibooru block (500); backing off 15min")
        if status >= 400:
            self._back_off_failure()
            raise ImageSourceError(f"Derpibooru returned HTTP {status}")

        try:
            payload = response.json()
        except ValueError as exc:
            self._back_off_failure()
            raise ImageSourceError("invalid JSON from Derpibooru") from exc

        self._failure_backoff = 0.0  # a good response clears the exponential back-off
        return payload

    async def _request(self, url: str, params: dict, headers: dict) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(url, params=params, headers=headers)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(url, params=params, headers=headers)

    def _cooldown(self, seconds: float) -> None:
        self._cooldown_until = self._clock() + seconds

    def _back_off_failure(self) -> None:
        self._failure_backoff = min(
            max(self._failure_backoff * 2, _FAILURE_BACKOFF_BASE), _FAILURE_BACKOFF_MAX
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
