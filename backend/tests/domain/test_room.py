"""Domain rules for Room — membership, ready-player collection, game lifecycle."""

import pytest

from app.domain.room import Room
from app.domain.user import User


def make_user(name: str, ready: bool = False) -> User:
    user = User(uuid=name, name=name)
    user.ready = ready
    return user


def test_add_get_and_remove_user():
    room = Room("lobby")
    alice = make_user("alice")
    room.add_user(alice)
    assert room.get_user("alice") is alice
    assert room.remove_user("alice") is alice
    assert room.get_user("alice") is None
    assert room.remove_user("ghost") is None


def test_ready_users_filters_to_ready_only():
    room = Room("lobby")
    room.add_user(make_user("alice", ready=True))
    room.add_user(make_user("bob", ready=False))
    room.add_user(make_user("carol", ready=True))
    assert {u.name for u in room.ready_users()} == {"alice", "carol"}


def test_room_is_inactive_without_a_game():
    assert Room("lobby").active is False


def test_start_game_builds_players_from_ready_users():
    room = Room("lobby")
    room.add_user(make_user("alice", ready=True))
    room.add_user(make_user("bob", ready=True))
    room.add_user(make_user("carol", ready=False))  # spectator

    game = room.start_game(tags=["solo"], first_index=0)
    assert {p.name for p in game.players} == {"alice", "bob"}
    assert room.game is game
    assert room.active is True


def test_start_game_excludes_room_query_from_buckets():
    room = Room("lobby", query=["cute"])
    room.add_user(make_user("alice", ready=True))
    game = room.start_game(tags=["solo", "cute"], first_index=0)
    assert game.tag_buckets["tags"].tags == ["solo"]


def test_start_game_forwards_game_options():
    room = Room("lobby")
    room.add_user(make_user("alice", ready=True))
    game = room.start_game(tags=["solo"], first_index=0, elimination_threshold=1)
    assert game.elimination_threshold == 1


def test_room_becomes_inactive_when_game_ends():
    room = Room("lobby")
    room.add_user(make_user("alice", ready=True))
    game = room.start_game(tags=["solo"], first_index=0)
    game.submit_guess("solo")  # only regular tag -> win
    assert game.is_over is True
    assert room.active is False  # finished game no longer counts as active


def test_end_game_clears_the_game():
    room = Room("lobby")
    room.add_user(make_user("alice", ready=True))
    room.start_game(tags=["solo"], first_index=0)
    room.end_game()
    assert room.game is None
    assert room.active is False


def test_start_game_without_ready_users_raises():
    room = Room("lobby")
    room.add_user(make_user("alice", ready=False))
    with pytest.raises(ValueError):
        room.start_game(tags=["solo"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
