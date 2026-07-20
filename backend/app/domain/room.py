"""A room: the people in it, its search config, and its current game.

Holds membership and the room↔game relationship. Fetching images and tracking
the currently displayed image live in the service layer; a room only needs the
image's tags handed to it when a game starts.
"""

from .game import Game
from .player import Player
from .user import User


class Room:
    """A room's membership, search config, and current game.

    Every argument defaults to off/empty rather than to a house policy: how
    strict a new room should be is a deployment choice, so the real values come
    from ``config.toml`` via the composition root's room factory. A bare
    ``Room(name)`` is the unopinionated baseline, not what players actually get.
    """

    def __init__(
        self,
        name: str,
        nsfw: bool = False,
        query: list[str] | None = None,
        turn_seconds: float | None = None,
        min_tag_count: int | None = None,
        min_score: int | None = None,
        rating_caps: dict[str, str] | None = None,
    ):
        self.name = name
        self.nsfw = nsfw
        self.query: list[str] = list(query or [])
        self.turn_seconds = turn_seconds
        # Provider search knobs: the room carries them, the image source reads
        # them. None means off; rating_caps maps an axis key to a level, both
        # from the source's own vocabulary, which the room never interprets.
        self.min_tag_count = min_tag_count
        self.min_score = min_score
        self.rating_caps: dict[str, str] = dict(rating_caps or {})
        self.users: dict[str, User] = {}
        self.game: Game | None = None

    @property
    def active(self) -> bool:
        """Whether a game is currently in progress."""
        return self.game is not None and not self.game.is_over

    def add_user(self, user: User) -> None:
        self.users[user.uuid] = user

    def remove_user(self, uuid: str) -> User | None:
        return self.users.pop(uuid, None)

    def get_user(self, uuid: str) -> User | None:
        return self.users.get(uuid)

    def ready_users(self) -> list[User]:
        return [user for user in self.users.values() if user.ready]

    def clear_ready(self) -> None:
        for user in self.users.values():
            user.ready = False

    def start_game(
        self,
        tags: list[str],
        first_index: int | None = None,
        query: list[str] | None = None,
        **game_options,
    ) -> Game:
        """Start a game with the room's ready users on the given image tags.

        ``query`` overrides the room's own for tag matching — the service passes
        a canonicalized form so an aliased search term still frees its tag.
        Callers should confirm ``ready_users()`` is non-empty first; an empty
        roster raises ``ValueError`` from ``Game``.
        """
        players = [Player(user) for user in self.ready_users()]
        self.game = Game(
            players,
            tags,
            self.query if query is None else query,
            first_index=first_index,
            **game_options,
        )
        return self.game

    def end_game(self) -> None:
        self.game = None
