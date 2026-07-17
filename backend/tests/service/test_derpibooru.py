"""DerpibooruImageSource: request shape, response mapping, and back-off rules.

No network: an ``httpx.MockTransport`` serves canned responses (and records the
outgoing request), and an injected clock drives the cooldown gate so the
mandatory back-off behavior is testable deterministically.
"""

import httpx
import pytest

from app.service.derpibooru import DerpibooruImageSource
from app.service.image_source import ImageSourceError

ONE_IMAGE = {
    "images": [
        {
            "id": 2887940,
            "tags": ["safe", "zipp storm", "pegasus", "pony", "g5", "artist:shikogo"],
            "representations": {
                "medium": "https://derpicdn.net/img/2022/6/15/2887940/medium.png",
                "full": "https://derpicdn.net/img/view/2022/6/15/2887940.png",
            },
            "source_url": "https://twitter.com/Shikogo/status/1537152019433136128",
        }
    ]
}


class Clock:
    """A hand-cranked monotonic clock for exercising the cooldown gate."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_source(handler, clock=None):
    """Build a source whose HTTP goes through a recording MockTransport handler."""
    requests = []

    def recording(request):
        requests.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(recording))
    source = DerpibooruImageSource(client=client, clock=clock or (lambda: 0.0))
    return source, requests


def respond(status=200, json=None, content=None):
    def handler(_request):
        if content is not None:
            return httpx.Response(status, content=content)
        return httpx.Response(status, json=json)

    return handler


# --- response mapping --------------------------------------------------------


async def test_maps_a_result_to_an_image():
    source, _ = make_source(respond(json=ONE_IMAGE))

    image = await source.random_image(["zipp storm"], nsfw=False)

    assert image.id == "2887940"
    assert "artist:shikogo" in image.tags
    assert image.thumb_url.endswith("/medium.png")
    assert image.full_url.endswith("/2887940.png")
    assert image.page_url == "https://derpibooru.org/images/2887940"
    assert image.source_url == "https://twitter.com/Shikogo/status/1537152019433136128"


async def test_no_matches_returns_none():
    source, _ = make_source(respond(json={"images": []}))

    assert await source.random_image(["nonexistent"], nsfw=False) is None


async def test_protocol_relative_urls_are_forced_to_https():
    payload = {
        "images": [
            {"id": 1, "tags": [], "representations": {"medium": "//cdn/x.png", "full": "//cdn/y.png"}}
        ]
    }
    source, _ = make_source(respond(json=payload))

    image = await source.random_image([], nsfw=False)

    assert image.thumb_url == "https://cdn/x.png"
    assert image.full_url == "https://cdn/y.png"


# --- request shape -----------------------------------------------------------


async def test_request_params_and_user_agent():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute", "pony"], nsfw=False)

    req = requests[0]
    assert req.url.params["q"] == "cute,pony"
    assert req.url.params["sf"] == "random"
    assert req.url.params["per_page"] == "1"
    assert "filter_id" not in req.url.params  # sfw sends no filter
    assert "derpigame" in req.headers["user-agent"]


async def test_empty_query_becomes_wildcard():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image([], nsfw=False)

    assert requests[0].url.params["q"] == "*"


async def test_nsfw_sends_the_everything_filter():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], nsfw=True)

    assert requests[0].url.params["filter_id"] == "56027"


# --- back-off rules ----------------------------------------------------------


async def test_transport_error_raises_and_backs_off():
    clock = Clock()

    def boom(_request):
        raise httpx.ConnectError("down")

    source, requests = make_source(boom, clock=clock)

    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], nsfw=False)

    # A retry before the back-off elapses must not touch the network at all.
    with pytest.raises(ImageSourceError, match="backing off"):
        await source.random_image(["x"], nsfw=False)
    assert len(requests) == 1  # second call short-circuited by the cooldown gate

    clock.advance(61)  # past the exponential-backoff cap
    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], nsfw=False)
    assert len(requests) == 2  # cooldown expired, request allowed through again


async def test_challenge_501_backs_off_five_seconds():
    clock = Clock()
    source, requests = make_source(respond(status=501, content=b"<html>challenge</html>"), clock=clock)

    with pytest.raises(ImageSourceError, match="challenge"):
        await source.random_image(["x"], nsfw=False)

    clock.advance(4)  # still inside the 5s window
    with pytest.raises(ImageSourceError, match="backing off"):
        await source.random_image(["x"], nsfw=False)
    assert len(requests) == 1  # no network during the challenge back-off

    clock.advance(2)  # now past 5s
    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], nsfw=False)
    assert len(requests) == 2


async def test_block_500_backs_off_fifteen_minutes():
    clock = Clock()
    source, requests = make_source(respond(status=500, content=b""), clock=clock)

    with pytest.raises(ImageSourceError, match="block"):
        await source.random_image(["x"], nsfw=False)

    clock.advance(14 * 60)  # still blocked
    with pytest.raises(ImageSourceError, match="backing off"):
        await source.random_image(["x"], nsfw=False)
    assert len(requests) == 1  # must not send during the block (it would reset it)

    clock.advance(2 * 60)  # past 15 minutes
    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], nsfw=False)
    assert len(requests) == 2


async def test_success_clears_the_failure_backoff():
    clock = Clock()
    calls = {"n": 0}

    def flaky(_request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("blip")
        return httpx.Response(200, json=ONE_IMAGE)

    source, _ = make_source(flaky, clock=clock)

    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], nsfw=False)
    clock.advance(2)  # clear the 1s failure cooldown
    assert (await source.random_image(["x"], nsfw=False)) is not None
    # After success the backoff is reset, so a later single failure starts at 1s again.
    assert source._failure_backoff == 0.0
