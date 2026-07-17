"""Per-game state for a user taking part in a game.

Created fresh when a game starts, so score and wrong-guess counts reset
naturally rather than being mutated back to zero on an existing object.
"""

from __future__ import annotations

from .user import User


class Player:
    def __init__(self, user: User):
        self.user = user
        self.score = 0
        self.wrong_guesses = 0

    @property
    def name(self) -> str:
        return self.user.name

    @property
    def uuid(self) -> str:
        return self.user.uuid

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Player(name={self.name!r}, score={self.score})"
