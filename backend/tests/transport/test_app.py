"""The composition root: settings reaching the objects they configure.

``create_app`` returns an opaque ASGI app, so these exercise the seams it uses
rather than the app itself — the room factory it hands the registry, and that it
builds at all with an injected image source.
"""

import httpx

from app.config import load_settings
from app.service.image_source import Image, StaticImageSource
from app.transport.app import _new_room, create_app


async def _run_lifespan(asgi_app):
    """Drive an ASGI app through startup then shutdown, returning the events it sent."""
    events = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])
    sent = []

    async def receive():
        return next(events)

    async def send(message):
        sent.append(message["type"])

    await asgi_app({"type": "lifespan"}, receive, send)
    return sent


def test_a_new_room_starts_with_the_configured_defaults():
    # Before this wiring the registry always built Room(name), so room defaults
    # in settings could never take effect.
    settings = load_settings(
        room_defaults={
            "nsfw": True,
            "query": ["pony"],
            "turn_seconds": 45.0,
            "min_tag_count": 20,
            "min_score": 100,
            # Both axes, so the result is the override alone — pydantic deep-merges
            # nested dicts across sources, and the shipped config caps both.
            "rating_caps": {"rating": "suggestive", "darkness": "grimdark"},
        }
    )

    room = _new_room(settings, "happy-derpy-pony")

    assert room.name == "happy-derpy-pony"
    assert room.nsfw is True
    assert room.query == ["pony"]
    assert room.turn_seconds == 45.0
    assert room.min_tag_count == 20
    assert room.min_score == 100
    assert room.rating_caps == {"rating": "suggestive", "darkness": "grimdark"}


def test_room_defaults_are_not_shared_between_rooms():
    # model_dump hands out fresh containers; a shared list would let one room's
    # query edit leak into every room opened afterwards.
    settings = load_settings(room_defaults={"query": ["pony"]})

    first = _new_room(settings, "a-b-c")
    second = _new_room(settings, "d-e-f")
    first.query.append("cute")

    assert second.query == ["pony"]


def test_create_app_builds_with_an_injected_image_source():
    image = Image(id="1", tags=["solo"], thumb_url="t", full_url="f")

    app = create_app(image_source=StaticImageSource([image]))

    assert app is not None


async def test_the_static_mount_falls_back_to_the_spa_shell(tmp_path):
    # The frontend routes on plain paths, so /room/<code> names no file and has
    # to reach index.html — without swallowing the assets that do exist.
    (tmp_path / "index.html").write_text("shell")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    image = Image(id="1", tags=["solo"], thumb_url="t", full_url="f")
    app = create_app(static_dir=tmp_path, image_source=StaticImageSource([image]))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        deep_link = await client.get("/room/happy-derpy-pony")
        asset = await client.get("/favicon.svg")

    assert deep_link.status_code == 200
    assert deep_link.text == "shell"
    assert asset.text == "<svg/>"


async def test_lifespan_closes_the_shared_booru_http_client(monkeypatch):
    # The client is built once in create_app and reused for every lookup, so the
    # shutdown hook must release its connection pool.
    closed = {"count": 0}

    class SpyClient(httpx.AsyncClient):
        async def aclose(self):
            closed["count"] += 1
            await super().aclose()

    monkeypatch.setattr(httpx, "AsyncClient", SpyClient)

    sent = await _run_lifespan(create_app())

    assert "lifespan.shutdown.complete" in sent
    assert closed["count"] == 1  # the one shared client, closed on shutdown
