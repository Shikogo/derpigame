"""Identity and lobby state for someone in a room.

A ``User`` is stable across games — it's the thing Phase 2 accounts/stats key
off. Per-game state (score, wrong guesses) lives on ``Player`` instead.
"""


class User:
    def __init__(self, uuid: str, name: str):
        self.uuid = uuid
        self.name = name
        self.ready = False
        self.viewing_results = False

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"User(name={self.name!r})"
