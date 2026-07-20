"""RoomRegistry: the in-memory room store the transport resolves rooms from."""

from app.domain.room import Room
from app.transport.registry import RoomRegistry


def test_create_stores_and_get_returns_the_same_room():
    registry = RoomRegistry()

    room = registry.create("happy-derpy-pony")

    assert room is not None
    assert registry.get("happy-derpy-pony") is room


def test_get_missing_room_is_none():
    assert RoomRegistry().get("nope-nope-fox") is None


def test_create_on_a_taken_name_returns_none():
    registry = RoomRegistry()
    first = registry.create("happy-derpy-pony")

    clash = registry.create("happy-derpy-pony")

    assert clash is None
    assert registry.get("happy-derpy-pony") is first  # original untouched


def test_remove_drops_the_room():
    registry = RoomRegistry()
    registry.create("happy-derpy-pony")

    registry.remove("happy-derpy-pony")

    assert registry.get("happy-derpy-pony") is None


def test_rooms_are_built_by_the_injected_factory():
    # How a room is configured is the composition root's business, not the
    # registry's — it just calls what it was handed.
    registry = RoomRegistry(lambda name: Room(name, nsfw=True, turn_seconds=42.0))

    room = registry.create("happy-derpy-pony")

    assert room.nsfw is True
    assert room.turn_seconds == 42.0
