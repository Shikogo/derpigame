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
from app.service.errors import NotYourTurn
from app.service.image_source import Image, ImageSource, ImageSourceError
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
        self._current_image: dict[str, Image] = {}  # image on display, per room

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
        self._current_image[room.name] = image
        await self._deliver(room, game.start(), lead=[_image_started_payload(image)])

    async def submit_guess(self, room: Room, user_uuid: str, guess: str) -> None:
        """Apply a guess from the active player; raise ``NotYourTurn`` otherwise."""
        guess = guess.strip()
        if not guess:
            return  # blank submission — never a strike
        game = room.game
        if game is None or game.is_over:
            return
        if game.active_player.uuid != user_uuid:
            raise NotYourTurn(game.active_player)
        await self._deliver(room, game.submit_guess(guess))

    async def handle_timeout(self, room: Room) -> None:
        """The active turn ran out of time. Invoked by the turn timer."""
        game = room.game
        if game is None or game.is_over:
            return
        await self._deliver(room, game.timeout())

    async def stop_game(self, room: Room) -> None:
        """Abort the in-progress game and return the room to the lobby.

        An aborted round still reveals the image (licensing + so a dropped image
        can still be tracked down), unlike an emptied room, which has no one left
        to reveal to.
        """
        if not room.active:
            return
        self._drop_timer(room.name)
        room.end_game()
        payloads: list[dict] = [{"type": "game_aborted"}]
        image = self._current_image.pop(room.name, None)
        if image is not None:
            payloads.append(_image_revealed_payload(image))
        await self._emitter.emit(room.name, payloads)

    async def _deliver(self, room: Room, events: list, *, lead: list[dict] | None = None) -> None:
        payloads = list(lead or []) + serialize_events(events)
        if any(isinstance(event, GameOver) for event in events):
            image = self._current_image.pop(room.name, None)
            if image is not None:
                payloads.append(_image_revealed_payload(image))
        try:
            if payloads:
                await self._emitter.emit(room.name, payloads)
        finally:
            # Re-arm even if emit fails, so a broken emit can't strand a turn
            # with no timer to advance it.
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

    def cancel_room(self, room_name: str) -> None:
        """Release a room's turn timer and image when it's abandoned or torn down."""
        self._drop_timer(room_name)
        self._current_image.pop(room_name, None)

    def shutdown(self) -> None:
        """Cancel every pending turn timer (app shutdown, or test cleanup)."""
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        self._current_image.clear()


def _image_started_payload(image: Image) -> dict:
    """The picture to display — deliberately without any answer-revealing tags."""
    return {
        "type": "image_started",
        "id": image.id,
        "thumb_url": image.thumb_url,
        "full_url": image.full_url,
    }


_ARTIST_PREFIX = "artist:"


def _image_revealed_payload(image: Image) -> dict:
    """Attribution shown once the image is no longer a secret (game end/abort)."""
    artists = [
        tag[len(_ARTIST_PREFIX):]
        for tag in image.tags
        if tag.startswith(_ARTIST_PREFIX)
    ]
    return {
        "type": "image_revealed",
        "artists": artists,
        "source_url": image.source_url,
        "page_url": image.page_url,
    }
