"""A minimal async Derpibooru image source.

Fetches a random image matching a room's query straight from Derpibooru's REST
search API with ``httpx`` — no blocking calls inside the event loop, and no
dependency on the legacy sync ``derpibooru`` package.

It is deliberately lean, but it does honor Derpibooru's mandatory back-off rules,
because ignoring them gets the server's IP banned: a cooldown gate refuses to
touch the network while we owe the server a back-off. A 501 anti-bot challenge
means stay silent ≥5s; a 500 means we're IP-blocked ≥15min and *any* request
during the block resets that timer, so we must not send one. Response caching and
live alias resolution are still Phase 3.
"""

import time

import httpx

from app.service.image_source import Image, ImageSource, ImageSourceError

_SEARCH_URL = "https://derpibooru.org/api/v1/json/search/images"
_USER_AGENT = "derpigame/0.1 (https://github.com/Shikogo/derpigame)"
# Derpibooru system filter that shows everything, incl. explicit — used for nsfw
# rooms. Sfw rooms send no filter and get the site default (hides explicit).
_EVERYTHING_FILTER_ID = "56027"

# Back-off durations (seconds) per Derpibooru's API rules.
_CHALLENGE_BACKOFF = 5.0  # 501 text/html anti-bot challenge: silence ≥5s
_BLOCK_BACKOFF = 15 * 60.0  # 500 empty body: IP blocked ≥15min; a request resets it
_FAILURE_BACKOFF_BASE = 1.0  # other failures back off exponentially from here...
_FAILURE_BACKOFF_MAX = 60.0  # ...capped here


class DerpibooruImageSource(ImageSource):
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

        payload = await self._get(params)
        images = payload.get("images") or []
        if not images:
            return None
        return _to_image(images[0])

    def _guard_cooldown(self) -> None:
        remaining = self._cooldown_until - self._clock()
        if remaining > 0:
            raise ImageSourceError(f"backing off from Derpibooru for {remaining:.0f}s")

    async def _get(self, params: dict) -> dict:
        headers = {"User-Agent": _USER_AGENT}
        try:
            response = await self._request(params, headers)
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

    async def _request(self, params: dict, headers: dict) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(_SEARCH_URL, params=params, headers=headers)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(_SEARCH_URL, params=params, headers=headers)

    def _cooldown(self, seconds: float) -> None:
        self._cooldown_until = self._clock() + seconds

    def _back_off_failure(self) -> None:
        self._failure_backoff = min(
            max(self._failure_backoff * 2, _FAILURE_BACKOFF_BASE), _FAILURE_BACKOFF_MAX
        )
        self._cooldown(self._failure_backoff)


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
