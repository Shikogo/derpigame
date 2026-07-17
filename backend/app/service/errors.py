"""Errors for player actions the service refuses to apply.

Unlike game events, which the whole room sees and which flow through the
emitter, a rejected action is a reply to the one caller who attempted it. These
are raised so the transport can translate them into an acknowledgement to that
caller alone, rather than broadcasting a correction the rest of the room would
see spuriously.
"""

from app.domain.player import Player


class GameActionError(Exception):
    """Base for a player action the service refuses to apply."""


class NotYourTurn(GameActionError):
    """A guess arrived from someone who isn't the active player."""

    def __init__(self, active_player: Player):
        self.active_player = active_player
        super().__init__(f"it is {active_player.name}'s turn")
