"""Orchestration: turn user actions into fetch → mutate domain → emit → time.

The domain says *what happens* (returns events) and never touches I/O; this
service decides *what to do when*. It pulls an image for a new game, routes
guesses and timeouts through the one path that mutates a ``Game``, serializes the
resulting events to the emitter, and drives the turn timer. Because guesses and
the timer both land here on a single event loop, turn advancement can't race.
"""

from app.domain.events import GameOver, TurnStarted
from app.domain.room import Room
from app.domain.tag_taxonomy import TagTaxonomy
from app.service.emitter import EventEmitter
from app.service.image_source import ImageSource, ImageSourceError
from app.service.serialization import serialize_events
from app.service.turn_timer import TurnTimer

DEFAULT_TURN_SECONDS = 30.0


class GameService:
    def __init__(
        self,
        image_source: ImageSource,
        emitter: EventEmitter,
        *,
        turn_seconds: float = DEFAULT_TURN_SECONDS,
        game_options: dict | None = None,
    ):
        self._images = image_source
        self._emitter = emitter
        self._turn_seconds = turn_seconds
        self._game_options = dict(game_options or {})
        self._timers: dict[str, TurnTimer] = {}

    async def start_game(
        self,
        room: Room,
        *,
        taxonomy: TagTaxonomy | None = None,
        first_index: int | None = None,
    ) -> None:
        """Fetch an image, open a game for the room's ready players, announce it."""
        if room.active:
            return  # a game is already in progress
        try:
            image = await self._images.random_image(room.query, nsfw=room.nsfw)
        except ImageSourceError:
            await self._emitter.emit(room.name, [{"type": "image_error"}])
            return
        if image is None:
            await self._emitter.emit(
                room.name, [{"type": "no_image", "query": list(room.query)}]
            )
            return

        options = dict(self._game_options)
        if taxonomy is not None:
            options["taxonomy"] = taxonomy
        game = room.start_game(image.tags, first_index=first_index, **options)
        await self._deliver(room, game.start())

    async def submit_guess(self, room: Room, user_uuid: str, guess: str) -> None:
        """Apply a guess, but only from the player whose turn it is."""
        game = room.game
        if game is None or game.is_over:
            return
        if game.active_player.uuid != user_uuid:
            return  # not this player's turn — ignore
        await self._deliver(room, game.submit_guess(guess))

    async def handle_timeout(self, room: Room) -> None:
        """The active turn ran out of time. Invoked by the turn timer."""
        game = room.game
        if game is None or game.is_over:
            return
        await self._deliver(room, game.timeout())

    async def _deliver(self, room: Room, events: list) -> None:
        if events:
            await self._emitter.emit(room.name, serialize_events(events))
        self._reschedule(room, events)

    def _reschedule(self, room: Room, events: list) -> None:
        """Arm the timer for a fresh turn, or drop it once the game is over.

        A turn only resets its clock when it actually changes (a ``TurnStarted``
        in the batch), so a rejected no-op guess doesn't let a player refill
        their own timer.
        """
        if any(isinstance(event, GameOver) for event in events):
            self._drop_timer(room.name)
        elif any(isinstance(event, TurnStarted) for event in events):
            timer = self._timers.setdefault(room.name, TurnTimer())
            timer.arm(self._turn_seconds, lambda: self.handle_timeout(room))

    def _drop_timer(self, room_name: str) -> None:
        timer = self._timers.pop(room_name, None)
        if timer is not None:
            timer.cancel()

    def shutdown(self) -> None:
        """Cancel every pending turn timer (app shutdown, or test cleanup)."""
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
