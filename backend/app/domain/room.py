"""A room: the people in it, its search config, and its current game.

Holds membership and the room↔game relationship. Fetching images and tracking
the currently displayed image live in the service layer; a room only needs the
image's tags handed to it when a game starts.
"""

from .game import Game
from .player import Player
from .user import User


class Room:
    def __init__(
        self,
        name: str,
        nsfw: bool = False,
        query: list[str] | None = None,
    ):
        self.name = name
        self.nsfw = nsfw
        self.query: list[str] = list(query or [])
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

    def start_game(
        self,
        tags: list[str],
        first_index: int | None = None,
        **game_options,
    ) -> Game:
        """Start a game with the room's ready users on the given image tags.

        Callers should confirm ``ready_users()`` is non-empty first; an empty
        roster raises ``ValueError`` from ``Game``.
        """
        players = [Player(user) for user in self.ready_users()]
        self.game = Game(
            players,
            tags,
            self.query,
            first_index=first_index,
            **game_options,
        )
        return self.game

    def end_game(self) -> None:
        self.game = None
