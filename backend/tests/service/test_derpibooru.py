"""DerpibooruClient: request shape, response mapping, alias resolution, back-off.

No network: an ``httpx.MockTransport`` serves canned responses (and records the
outgoing request), and an injected clock drives the cooldown gate so the
mandatory back-off behavior is testable deterministically.
"""

import httpx
import pytest

from app.config import DerpibooruSettings
from app.service.derpibooru import DerpibooruClient
from app.service.image_source import ImageSourceError, SearchOptions

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


async def _no_sleep(_seconds):
    """Default test sleep: let the spacing gate 'wait' without real time passing."""


def coupled_sleep(clock):
    """A fake sleep that records its waits and advances ``clock``, as real time would."""
    waits = []

    async def sleep(seconds):
        waits.append(seconds)
        clock.advance(seconds)

    return sleep, waits


def make_source(handler, clock=None, config=None, sleep=None):
    """Build a source whose HTTP goes through a recording MockTransport handler."""
    requests = []

    def recording(request):
        requests.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(recording))
    source = DerpibooruClient(
        client=client, clock=clock or (lambda: 0.0), sleep=sleep or _no_sleep, config=config
    )
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

    image = await source.random_image(["zipp storm"], options=SearchOptions())

    assert image.id == "2887940"
    assert "artist:shikogo" in image.tags
    assert image.thumb_url.endswith("/medium.png")
    assert image.full_url.endswith("/2887940.png")
    assert image.page_url == "https://derpibooru.org/images/2887940"
    assert image.source_url == "https://twitter.com/Shikogo/status/1537152019433136128"


async def test_no_matches_returns_none():
    source, _ = make_source(respond(json={"images": []}))

    assert await source.random_image(["nonexistent"], options=SearchOptions()) is None


async def test_protocol_relative_urls_are_forced_to_https():
    payload = {
        "images": [
            {
                "id": 1,
                "tags": [],
                "representations": {"medium": "//cdn/x.png", "full": "//cdn/y.png"},
            }
        ]
    }
    source, _ = make_source(respond(json=payload))

    image = await source.random_image([], options=SearchOptions())

    assert image.thumb_url == "https://cdn/x.png"
    assert image.full_url == "https://cdn/y.png"


# --- request shape -----------------------------------------------------------


async def test_request_params_and_user_agent():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute", "pony"], options=SearchOptions())

    req = requests[0]
    assert req.url.params["q"] == "cute,pony,-mime_type:video/webm"
    assert req.url.params["sf"] == "random"
    assert req.url.params["per_page"] == "1"
    assert req.url.params["filter_id"] == "100073"  # sfw gets the modern default
    assert "derpigame" in req.headers["user-agent"]


async def test_empty_query_becomes_wildcard():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image([], options=SearchOptions())

    assert requests[0].url.params["q"] == "*,-mime_type:video/webm"


async def test_videos_are_excluded_from_every_search():
    """Videos are unviewable (no still representation), so they never get picked."""
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], options=SearchOptions())
    await source.random_image([], options=SearchOptions(nsfw=True))

    assert all("-mime_type:video/webm" in r.url.params["q"] for r in requests)


async def test_settings_left_off_send_no_extra_terms():
    """The regression guard: an unset room queries exactly as it always has."""
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], options=SearchOptions())

    assert requests[0].url.params["q"] == "cute,-mime_type:video/webm"


async def test_tag_count_and_score_bounds_become_search_terms():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], options=SearchOptions(min_tag_count=15, min_score=10))

    q = requests[0].url.params["q"]
    assert "tag_count.gte:15" in q and "score.gte:10" in q


async def test_a_zero_score_bound_is_a_real_filter_not_an_off_switch():
    """score.gte:0 excludes downvoted images, so 0 must survive as a term."""
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], options=SearchOptions(min_score=0))

    assert "score.gte:0" in requests[0].url.params["q"]


async def test_a_negative_score_bound_is_kept():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], options=SearchOptions(min_score=-50))

    assert "score.gte:-50" in requests[0].url.params["q"]


async def test_a_rating_cap_excludes_the_levels_above_it():
    """Exclusion, not positive selection: an image rated on neither axis still shows.

    A positive `(safe || suggestive)` would drop the tens of thousands of images
    carrying only a darkness tag, and OR-ing the two axes to fix that would let
    an explicit image back in through its darkness tag.
    """
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], options=SearchOptions(rating_caps={"rating": "suggestive"}))

    assert requests[0].url.params["q"] == ("cute,-mime_type:video/webm,-questionable,-explicit")


async def test_the_axes_are_capped_independently():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(
        ["cute"],
        options=SearchOptions(rating_caps={"rating": "questionable", "darkness": "semi-grimdark"}),
    )

    assert requests[0].url.params["q"] == (
        "cute,-mime_type:video/webm,-explicit,-grimdark,-grotesque"
    )


async def test_the_top_of_an_axis_caps_nothing():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(
        ["cute"],
        options=SearchOptions(rating_caps={"rating": "explicit", "darkness": "grotesque"}),
    )

    assert requests[0].url.params["q"] == "cute,-mime_type:video/webm"


async def test_every_setting_at_once():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(
        ["cute", "pony"],
        options=SearchOptions(
            min_tag_count=15,
            min_score=10,
            rating_caps={"rating": "safe", "darkness": "none"},
        ),
    )

    assert requests[0].url.params["q"] == (
        "cute,pony,-mime_type:video/webm,tag_count.gte:15,score.gte:10,"
        "-suggestive,-questionable,-explicit,"
        "-semi-grimdark,-grimdark,-grotesque"
    )


async def test_nsfw_sends_the_nsfw_filter():
    source, requests = make_source(respond(json=ONE_IMAGE))

    await source.random_image(["cute"], options=SearchOptions(nsfw=True))

    assert requests[0].url.params["filter_id"] == "232619"


# --- back-off rules ----------------------------------------------------------


async def test_transport_error_raises_and_backs_off():
    clock = Clock()

    def boom(_request):
        raise httpx.ConnectError("down")

    source, requests = make_source(boom, clock=clock)

    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], options=SearchOptions())

    # A retry before the back-off elapses must not touch the network at all.
    with pytest.raises(ImageSourceError, match="backing off"):
        await source.random_image(["x"], options=SearchOptions())
    assert len(requests) == 1  # second call short-circuited by the cooldown gate

    clock.advance(61)  # past the exponential-backoff cap
    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], options=SearchOptions())
    assert len(requests) == 2  # cooldown expired, request allowed through again


async def test_challenge_501_backs_off_five_seconds():
    clock = Clock()
    source, requests = make_source(
        respond(status=501, content=b"<html>challenge</html>"), clock=clock
    )

    with pytest.raises(ImageSourceError, match="challenge"):
        await source.random_image(["x"], options=SearchOptions())

    clock.advance(4)  # still inside the 5s window
    with pytest.raises(ImageSourceError, match="backing off"):
        await source.random_image(["x"], options=SearchOptions())
    assert len(requests) == 1  # no network during the challenge back-off

    clock.advance(2)  # now past 5s
    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], options=SearchOptions())
    assert len(requests) == 2


async def test_block_500_backs_off_fifteen_minutes():
    clock = Clock()
    source, requests = make_source(respond(status=500, content=b""), clock=clock)

    with pytest.raises(ImageSourceError, match="block"):
        await source.random_image(["x"], options=SearchOptions())

    clock.advance(14 * 60)  # still blocked
    with pytest.raises(ImageSourceError, match="backing off"):
        await source.random_image(["x"], options=SearchOptions())
    assert len(requests) == 1  # must not send during the block (it would reset it)

    clock.advance(2 * 60)  # past 15 minutes
    with pytest.raises(ImageSourceError):
        await source.random_image(["x"], options=SearchOptions())
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
        await source.random_image(["x"], options=SearchOptions())
    clock.advance(2)  # clear the 1s failure cooldown
    assert (await source.random_image(["x"], options=SearchOptions())) is not None
    # After success the backoff is reset, so a later single failure starts at 1s again.
    assert source._failure_backoff == 0.0


# --- request spacing ---------------------------------------------------------


async def test_requests_are_spaced_to_stay_under_the_rate_limit():
    """A burst is throttled to one request per interval; the first still fires now."""
    clock = Clock()
    sleep, waits = coupled_sleep(clock)
    source, requests = make_source(respond(json=ONE_IMAGE), clock=clock, sleep=sleep)

    for _ in range(3):
        await source.random_image(["x"], options=SearchOptions())

    assert len(requests) == 3  # every request is sent, just spread out
    assert waits == [0.5, 0.5]  # first is immediate; each later one waits an interval


async def test_a_backoff_refusal_skips_the_spacing_gate():
    """The gate sits after the cooldown guard: a refused call neither sends nor sleeps."""
    clock = Clock()
    sleep, waits = coupled_sleep(clock)
    source, requests = make_source(respond(status=500, content=b""), clock=clock, sleep=sleep)

    with pytest.raises(ImageSourceError, match="block"):  # first call trips the 15min block
        await source.random_image(["x"], options=SearchOptions())

    with pytest.raises(ImageSourceError, match="backing off"):  # refused during the block
        await source.random_image(["x"], options=SearchOptions())

    assert len(requests) == 1  # the refusal sent nothing...
    assert waits == []  # ...and never reached the spacing gate to sleep


# --- alias resolution --------------------------------------------------------

BIG_MAC_TAG = {
    "total": 1,
    "tags": [{"id": 20869, "name": "big macintosh", "aliases": ["bm", "big+mac"]}],
}


def test_slug_decoding_reverses_derpibooru_escapes():
    from app.service.derpibooru import _slug_to_name

    assert _slug_to_name("big+mac") == "big mac"  # "+" is the space escape
    assert _slug_to_name("oc-colon-fluffle+puff") == "oc:fluffle puff"
    assert _slug_to_name("artist-colon-atryl") == "artist:atryl"


async def test_canonicalize_maps_an_alias_to_the_canonical_name():
    source, requests = make_source(respond(json=BIG_MAC_TAG))

    assert await source.canonicalize("bm") == "big macintosh"

    req = requests[0]
    assert req.url.path == "/api/v1/json/search/tags"
    assert req.url.params["q"] == "aliases:bm"  # unquoted; quoting returns nothing


async def test_canonicalize_passes_through_when_there_is_no_alias():
    source, _ = make_source(respond(json={"total": 0, "tags": []}))

    assert await source.canonicalize("pony") == "pony"


async def test_canonicalize_caches_the_lookup():
    source, requests = make_source(respond(json=BIG_MAC_TAG))

    assert await source.canonicalize("bm") == "big macintosh"
    assert await source.canonicalize("bm") == "big macintosh"

    assert len(requests) == 1  # second call served from the cache


async def test_canonicalize_caches_sibling_aliases_from_one_lookup():
    source, requests = make_source(respond(json=BIG_MAC_TAG))

    await source.canonicalize("bm")  # one lookup teaches every sibling alias
    assert await source.canonicalize("big mac") == "big macintosh"

    assert len(requests) == 1  # the decoded sibling needs no request of its own


async def test_canonicalize_negative_result_is_cached():
    source, requests = make_source(respond(json={"total": 0, "tags": []}))

    await source.canonicalize("pony")
    await source.canonicalize("pony")

    assert len(requests) == 1  # a "no alias" answer is remembered too


async def test_the_alias_cache_evicts_the_least_recently_used_entry():
    """The cache is bounded: past the cap the least-recently-used entry is dropped."""
    config = DerpibooruSettings(alias_cache_max=2)
    source, requests = make_source(respond(json={"total": 0, "tags": []}), config=config)

    await source.canonicalize("a")
    await source.canonicalize("b")
    await source.canonicalize("a")  # touch 'a', so 'b' becomes the least-recently-used
    await source.canonicalize("c")  # over the cap of 2: evicts 'b', keeps 'a' and 'c'
    assert len(requests) == 3

    await source.canonicalize("a")  # the touch saved it from eviction: still cached
    assert len(requests) == 3  # no new request

    await source.canonicalize("b")  # evicted, so it must ask the network again
    assert len(requests) == 4


async def test_canonicalize_returns_input_during_a_cooldown():
    clock = Clock()
    source, requests = make_source(respond(status=500, content=b""), clock=clock)

    with pytest.raises(ImageSourceError):  # an image fetch trips the 15min block
        await source.random_image(["x"], options=SearchOptions())

    assert await source.canonicalize("bm") == "bm"  # degrade, don't raise
    assert len(requests) == 1  # resolving sent nothing during the block


async def test_canonicalize_returns_input_on_transport_error():
    def boom(_request):
        raise httpx.ConnectError("down")

    source, _ = make_source(boom)

    assert await source.canonicalize("bm") == "bm"  # best-effort: no raise


# --- configuration ------------------------------------------------------------


async def test_configured_credentials_and_identity_reach_the_request():
    config = DerpibooruSettings(api_key="s3cret", user_agent="test-agent/9")
    source, requests = make_source(respond(json=ONE_IMAGE), config=config)

    await source.random_image(["cute"], options=SearchOptions())

    assert requests[0].url.params["key"] == "s3cret"
    assert requests[0].headers["user-agent"] == "test-agent/9"


async def test_configured_filter_ids_are_used_per_room_rating():
    config = DerpibooruSettings(default_filter_id="111", nsfw_filter_id="222")
    source, requests = make_source(respond(json=ONE_IMAGE), config=config)

    await source.random_image([], options=SearchOptions(nsfw=False))
    await source.random_image([], options=SearchOptions(nsfw=True))

    assert requests[0].url.params["filter_id"] == "111"
    assert requests[1].url.params["filter_id"] == "222"


async def test_configured_backoff_governs_the_cooldown():
    # The back-offs are API-compliance rules, so a config value that didn't reach
    # the gate would leave us hammering a source that asked for silence.
    clock = Clock()
    config = DerpibooruSettings(challenge_backoff=42.0)
    source, requests = make_source(
        respond(status=501, content="<html/>"), clock=clock, config=config
    )

    with pytest.raises(ImageSourceError, match="backing off 42s"):
        await source.random_image([], options=SearchOptions())
    assert len(requests) == 1

    clock.advance(41.0)  # still inside the window: refused without touching the network
    with pytest.raises(ImageSourceError, match="backing off"):
        await source.random_image([], options=SearchOptions())
    assert len(requests) == 1

    clock.advance(2.0)  # past it: the request is attempted again
    with pytest.raises(ImageSourceError):
        await source.random_image([], options=SearchOptions())
    assert len(requests) == 2
