"""The composition root: settings reaching the objects they configure.

``create_app`` returns an opaque ASGI app, so these exercise the seams it uses
rather than the app itself — the room factory it hands the registry, and that it
builds at all with an injected image source.
"""

from app.config import load_settings
from app.service.image_source import Image, StaticImageSource
from app.transport.app import _new_room, create_app


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
            "rating_caps": {"rating": "suggestive"},
        }
    )

    room = _new_room(settings, "happy-derpy-pony")

    assert room.name == "happy-derpy-pony"
    assert room.nsfw is True
    assert room.query == ["pony"]
    assert room.turn_seconds == 45.0
    assert room.min_tag_count == 20
    assert room.min_score == 100
    assert room.rating_caps == {"rating": "suggestive"}


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
