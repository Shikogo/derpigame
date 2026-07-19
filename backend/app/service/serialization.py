"""Translate domain events into JSON-serializable wire payloads.

Each payload carries a ``type`` discriminator plus flat data fields; the Vue
client switches on ``type`` and owns all display text. Field names are
snake_case, matching the domain, so there's no case-translation layer to drift.
Serialization lives here, never on the domain events themselves.
"""

from functools import singledispatch

from app.domain.events import (
    CorrectGuess,
    GameOver,
    GameStarted,
    GuessRejected,
    NearMiss,
    PlayerEliminated,
    Timeout,
    TurnStarted,
    WrongGuess,
)
from app.domain.player import Player


def serialize_player(player: Player) -> dict:
    return {
        "uuid": player.uuid,
        "name": player.name,
        "score": player.score,
        "wrong_guesses": player.wrong_guesses,
    }


@singledispatch
def serialize_event(event) -> dict:
    raise TypeError(f"no serializer registered for {type(event).__name__}")


@serialize_event.register
def _(event: GameStarted) -> dict:
    return {
        "type": "game_started",
        "first_player": serialize_player(event.first_player),
        "players": [serialize_player(p) for p in event.players],
        "tag_count": event.tag_count,
        "bonus_counts": event.bonus_counts,
        "query": event.query,
    }


@serialize_event.register
def _(event: TurnStarted) -> dict:
    return {"type": "turn_started", "player": serialize_player(event.player)}


@serialize_event.register
def _(event: GuessRejected) -> dict:
    return {"type": "guess_rejected", "guess": event.guess, "reason": event.reason.value}


@serialize_event.register
def _(event: CorrectGuess) -> dict:
    return {
        "type": "correct_guess",
        "player": serialize_player(event.player),
        "guess": event.guess,
        "tag_type": event.tag_type,
        "remaining": event.remaining,
    }


@serialize_event.register
def _(event: WrongGuess) -> dict:
    return {
        "type": "wrong_guess",
        "player": serialize_player(event.player),
        "guess": event.guess,
        "wrong_count": event.wrong_count,
    }


@serialize_event.register
def _(event: NearMiss) -> dict:
    return {
        "type": "near_miss",
        "player": serialize_player(event.player),
        "guess": event.guess,
        "closeness": event.closeness,
    }


@serialize_event.register
def _(event: Timeout) -> dict:
    return {
        "type": "timeout",
        "player": serialize_player(event.player),
        "wrong_count": event.wrong_count,
    }


@serialize_event.register
def _(event: PlayerEliminated) -> dict:
    return {"type": "player_eliminated", "player": serialize_player(event.player)}


@serialize_event.register
def _(event: GameOver) -> dict:
    return {
        "type": "game_over",
        "win": event.win,
        "winners": [serialize_player(p) for p in event.winners],
        "standings": [serialize_player(p) for p in event.standings],
        "unguessed_tags": event.unguessed_tags,
    }


def serialize_events(events) -> list[dict]:
    return [serialize_event(event) for event in events]
