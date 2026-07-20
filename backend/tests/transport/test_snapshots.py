"""room_state: the whole-snapshot lobby view broadcast on any lobby change."""

from app.domain.room import Room
from app.domain.user import User
from app.transport.snapshots import room_state


def _room_with_users() -> Room:
    room = Room(
        "happy-derpy-pony", nsfw=True, query=["cute", "pony"], min_tag_count=15, min_score=10
    )
    alice = User("ua", "Alice")
    alice.ready = True
    room.add_user(alice)
    room.add_user(User("ub", "Bob"))
    return room


def test_snapshot_carries_config_and_roster():
    snap = room_state(_room_with_users())

    assert snap["room"] == "happy-derpy-pony"
    assert snap["query"] == ["cute", "pony"]
    assert snap["nsfw"] is True
    assert snap["min_tag_count"] == 15
    assert snap["min_score"] == 10
    assert snap["rating_caps"] == {}  # uncapped until a host says otherwise
    assert snap["in_progress"] is False
    assert snap["users"] == [
        {"uuid": "ua", "name": "Alice", "ready": True},
        {"uuid": "ub", "name": "Bob", "ready": False},
    ]


def test_in_progress_tracks_an_active_game():
    room = _room_with_users()
    room.start_game(["solo", "twilight"], first_index=0)

    assert room_state(room)["in_progress"] is True
