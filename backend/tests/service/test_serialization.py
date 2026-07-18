"""Tests that domain events serialize to the expected wire payloads."""

import pytest

from app.domain.events import (
    CorrectGuess,
    GameOver,
    GameStarted,
    GuessRejected,
    PlayerEliminated,
    RejectReason,
    Timeout,
    TurnStarted,
    WrongGuess,
)
from app.domain.player import Player
from app.domain.user import User
from app.service.serialization import serialize_event, serialize_events


def make_player(name: str, score: int = 0, wrong: int = 0) -> Player:
    player = Player(User(uuid=name, name=name))
    player.score = score
    player.wrong_guesses = wrong
    return player


def test_player_is_serialized_with_identity_and_state():
    payload = serialize_event(TurnStarted(make_player("alice", score=2, wrong=1)))
    assert payload == {
        "type": "turn_started",
        "player": {"uuid": "alice", "name": "alice", "score": 2, "wrong_guesses": 1},
    }


def test_game_started_reports_counts_and_first_player():
    payload = serialize_event(
        GameStarted(
            first_player=make_player("alice"),
            tag_count=5,
            bonus_counts={"artists": 1, "ocs": 0},
            query=["cute"],
            players=[make_player("alice"), make_player("bob")],
        )
    )
    assert payload["type"] == "game_started"
    assert payload["tag_count"] == 5
    assert payload["bonus_counts"] == {"artists": 1, "ocs": 0}
    assert payload["query"] == ["cute"]
    assert payload["first_player"]["name"] == "alice"
    assert [p["name"] for p in payload["players"]] == ["alice", "bob"]


def test_guess_rejected_uses_reason_value():
    payload = serialize_event(GuessRejected("safe", RejectReason.RATING_TAG))
    assert payload == {"type": "guess_rejected", "guess": "safe", "reason": "rating_tag"}


def test_correct_guess_payload():
    payload = serialize_event(
        CorrectGuess(make_player("alice", score=1), "solo", "tags", remaining=3)
    )
    assert payload["type"] == "correct_guess"
    assert payload["guess"] == "solo"
    assert payload["tag_type"] == "tags"
    assert payload["remaining"] == 3


def test_wrong_guess_carries_closeness():
    payload = serialize_event(WrongGuess(make_player("bob"), "twiligth", 2, closeness=85))
    assert payload["type"] == "wrong_guess"
    assert payload["wrong_count"] == 2
    assert payload["closeness"] == 85


def test_timeout_payload():
    payload = serialize_event(Timeout(make_player("bob", wrong=3), 3))
    assert payload == {
        "type": "timeout",
        "player": {"uuid": "bob", "name": "bob", "score": 0, "wrong_guesses": 3},
        "wrong_count": 3,
    }


def test_player_eliminated_payload():
    payload = serialize_event(PlayerEliminated(make_player("bob")))
    assert payload["type"] == "player_eliminated"
    assert payload["player"]["name"] == "bob"


def test_game_over_serializes_winners_and_standings():
    alice = make_player("alice", score=3)
    bob = make_player("bob", score=1)
    payload = serialize_event(
        GameOver(win=True, winners=[alice], standings=[alice, bob], unguessed_tags=[])
    )
    assert payload["type"] == "game_over"
    assert payload["win"] is True
    assert [p["name"] for p in payload["winners"]] == ["alice"]
    assert [p["name"] for p in payload["standings"]] == ["alice", "bob"]
    assert payload["unguessed_tags"] == []


def test_unregistered_event_raises():
    with pytest.raises(TypeError):
        serialize_event(object())


def test_serialize_events_maps_a_list():
    events = [TurnStarted(make_player("alice")), Timeout(make_player("alice"), 1)]
    payloads = serialize_events(events)
    assert [p["type"] for p in payloads] == ["turn_started", "timeout"]
