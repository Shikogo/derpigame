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
from app.service.serialization import serialize_events, serialize_player
from app.service.tag_resolver import NullTagResolver, TagResolver
from app.service.turn_timer import TurnTimer

DEFAULT_TURN_SECONDS = 60.0


class GameService:
    def __init__(
        self,
        image_source: ImageSource,
        emitter: EventEmitter,
        *,
        tag_resolver: TagResolver | None = None,
        turn_seconds: float = DEFAULT_TURN_SECONDS,
        game_options: dict | None = None,
    ):
        self._images = image_source
        self._resolver = tag_resolver or NullTagResolver()
        self._emitter = emitter
        self._turn_seconds = turn_seconds
        self._game_options = dict(game_options or {})
        self._timers: dict[str, TurnTimer] = {}
        self._current_image: dict[str, Image] = {}  # image on display, per room
        self._history: dict[str, list[dict]] = {}  # finished rounds, per room

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
        guess = await self._canonicalized(game, guess)
        await self._deliver(room, game.submit_guess(guess))

    async def _canonicalized(self, game, guess: str) -> str:
        """Map an unrecognized guess to its canonical tag; leave known ones alone.

        A guess the game already recognizes needs no external help, so only novel
        strings (aliases, typos) reach the resolver — which returns them unchanged
        when there's no alias or the lookup can't be made.
        """
        if game.recognizes(guess):
            return guess
        return await self._resolver.canonicalize(guess)

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
            self._record_round(room.name, image, None)  # aborted: no result
        await self._emitter.emit(room.name, payloads)

    def turn_seconds_for(self, room: Room) -> float:
        """The room's turn length, falling back to the deployment default."""
        return room.turn_seconds if room.turn_seconds is not None else self._turn_seconds

    async def _deliver(self, room: Room, events: list, *, lead: list[dict] | None = None) -> None:
        payloads = list(lead or []) + serialize_events(events)
        for payload in payloads:
            if payload["type"] == "game_started":
                payload["turn_seconds"] = self.turn_seconds_for(room)
        game_over = next((e for e in events if isinstance(e, GameOver)), None)
        if game_over is not None:
            image = self._current_image.pop(room.name, None)
            if image is not None:
                payloads.append(_image_revealed_payload(image))
                self._record_round(room.name, image, game_over)
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
            timer.arm(self.turn_seconds_for(room), lambda: self.handle_timeout(room))

    def _drop_timer(self, room_name: str) -> None:
        timer = self._timers.pop(room_name, None)
        if timer is not None:
            timer.cancel()

    def _record_round(self, room_name: str, image: Image, game_over: GameOver | None) -> None:
        """Append a finished round to the room's history (game over or abort)."""
        self._history.setdefault(room_name, []).append(_round_record(image, game_over))

    def room_history(self, room_name: str) -> list[dict]:
        """The room's finished rounds, oldest first — for the lobby snapshot."""
        return list(self._history.get(room_name, ()))

    def room_win_counts(self, room_name: str) -> list[dict]:
        """Wins per player across the room's finished rounds, most first."""
        return _tally_wins(self._history.get(room_name, ()))

    def game_snapshot(self, room: Room) -> dict | None:
        """An answer-safe view of the in-progress game for a (re)joining client.

        Carries the current image, roster with scores, whose turn it is, and
        remaining counts — never the unguessed goal tags. ``None`` when no game
        is running, so a lobby join sends nothing.
        """
        game = room.game
        image = self._current_image.get(room.name)
        if game is None or game.is_over or image is None:
            return None
        goal_key = game.taxonomy.goal_bucket
        goal_remaining = game.tag_buckets[goal_key].tag_count
        goal_guessed = sum(
            1 for tag in game.guessed_tags if game.taxonomy.bucket_for(tag) == goal_key
        )
        return {
            "type": "game_snapshot",
            "image": {
                "id": image.id,
                "thumb_url": image.thumb_url,
                "full_url": image.full_url,
            },
            "players": [
                serialize_player(p) for p in (*game.players, *game.eliminated_players)
            ],
            "active_player": serialize_player(game.active_player),
            "tag_count": goal_remaining + goal_guessed,  # original goal-bucket size
            "goal_remaining": goal_remaining,
            "bonus_counts": {
                key: bucket.tag_count
                for key, bucket in game.tag_buckets.items()
                if key != goal_key
            },
            "eliminated": [p.uuid for p in game.eliminated_players],
            "turn_seconds": self.turn_seconds_for(room),
        }

    def cancel_room(self, room_name: str) -> None:
        """Release a room's turn timer, image, and history when it's torn down."""
        self._drop_timer(room_name)
        self._current_image.pop(room_name, None)
        self._history.pop(room_name, None)

    def shutdown(self) -> None:
        """Cancel every pending turn timer (app shutdown, or test cleanup)."""
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        self._current_image.clear()
        self._history.clear()


def _image_started_payload(image: Image) -> dict:
    """The picture to display — deliberately without any answer-revealing tags."""
    return {
        "type": "image_started",
        "id": image.id,
        "thumb_url": image.thumb_url,
        "full_url": image.full_url,
    }


_ARTIST_PREFIX = "artist:"


def _artist_names(image: Image) -> list[str]:
    return [
        tag[len(_ARTIST_PREFIX):]
        for tag in image.tags
        if tag.startswith(_ARTIST_PREFIX)
    ]


def _image_revealed_payload(image: Image) -> dict:
    """Attribution shown once the image is no longer a secret (game end/abort)."""
    return {
        "type": "image_revealed",
        "artists": _artist_names(image),
        "source_url": image.source_url,
        "page_url": image.page_url,
    }


def _round_record(image: Image, game_over: GameOver | None) -> dict:
    """A finished round for the history: its link/attribution plus the result.

    ``game_over is None`` means the round was aborted — it has a link worth
    keeping but no winners or final standings.
    """
    return {
        "page_url": image.page_url,
        "source_url": image.source_url,
        "thumb_url": image.thumb_url,
        "artists": _artist_names(image),
        "win": game_over.win if game_over else False,
        "aborted": game_over is None,
        "winners": [serialize_player(p) for p in game_over.winners] if game_over else [],
        "standings": [serialize_player(p) for p in game_over.standings] if game_over else [],
    }


def _tally_wins(records) -> list[dict]:
    """Fold finished rounds into a win count per player (by uuid), most first."""
    tallies: dict[str, dict] = {}
    for record in records:
        for winner in record["winners"]:
            entry = tallies.get(winner["uuid"])
            if entry is None:
                tallies[winner["uuid"]] = {
                    "uuid": winner["uuid"],
                    "name": winner["name"],
                    "wins": 1,
                }
            else:
                entry["wins"] += 1
                entry["name"] = winner["name"]  # keep the most recent name
    return sorted(tallies.values(), key=lambda t: t["wins"], reverse=True)
