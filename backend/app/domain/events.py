"""Result objects describing what happened during a game action.

Domain methods return sequences of these instead of emitting or rendering.
The service/transport layers translate them into messages and socket events.
"""

from dataclasses import dataclass, field
from enum import Enum

from .player import Player


class GameEvent:
    """Base class for everything a game action can report."""


class RejectReason(str, Enum):
    ALREADY_GUESSED = "already_guessed"  # a tag that was already found
    ALREADY_WRONG = "already_wrong"  # a guess already tried and known wrong
    DEFAULT_TAG = "default_tag"
    RATING_TAG = "rating_tag"


@dataclass
class GameStarted(GameEvent):
    first_player: Player
    tag_count: int  # tags in the goal bucket — all must be guessed to win
    bonus_counts: dict[str, int]  # namespaced bucket key -> count, e.g. {"artists": 1}
    query: list[str]
    players: list[Player]  # full roster for the round; the rest of the room spectates


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
