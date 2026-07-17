"""Result objects describing what happened during a game action.

Domain methods return sequences of these instead of emitting or rendering.
The service/transport layers translate them into messages and socket events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .player import Player


class GameEvent:
    """Base class for everything a game action can report."""


class RejectReason(str, Enum):
    ALREADY_GUESSED = "already_guessed"
    DEFAULT_TAG = "default_tag"
    RATING_TAG = "rating_tag"


@dataclass
class GameStarted(GameEvent):
    first_player: Player
    tag_count: int
    artist_count: int
    oc_count: int
    query: list[str]


@dataclass
class TurnStarted(GameEvent):
    player: Player


@dataclass
class GuessRejected(GameEvent):
    guess: str
    reason: RejectReason


@dataclass
class CorrectGuess(GameEvent):
    player: Player
    guess: str
    tag_type: str  # bucket key: "tags" | "artists" | "ocs"
    remaining: int


@dataclass
class WrongGuess(GameEvent):
    player: Player
    guess: str
    wrong_count: int
    closeness: int = 0  # similarity %, 0 when not a near miss


@dataclass
class Timeout(GameEvent):
    player: Player
    wrong_count: int


@dataclass
class PlayerEliminated(GameEvent):
    player: Player


@dataclass
class GameOver(GameEvent):
    win: bool
    winners: list[Player]
    standings: list[Player]
    unguessed_tags: list[str] = field(default_factory=list)
