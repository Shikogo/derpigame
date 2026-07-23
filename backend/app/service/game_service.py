"""Orchestration: turn user actions into fetch → mutate domain → emit → time.

The domain says *what happens* (returns events) and never touches I/O; this
service decides *what to do when*. It pulls an image for a new game, routes
guesses and timeouts through the one path that mutates a ``Game``, serializes the
resulting events to the emitter, and drives the turn timer. Because guesses and
the timer both land here on a single event loop, turn advancement can't race.
"""

import logging
from collections.abc import Mapping

from app.config import LimitsSettings, RoomDefaults
from app.domain.events import GameOver, TurnStarted
from app.domain.room import Room
from app.domain.tag_taxonomy import TagTaxonomy
from app.service.emitter import EventEmitter
from app.service.errors import GameActionError, NotYourTurn
from app.service.image_source import Image, ImageSource, ImageSourceError, SearchOptions
from app.service.serialization import serialize_events, serialize_player
from app.service.sources import SourceBundle
from app.service.tag_resolver import NullTagResolver, TagResolver
from app.service.turn_timer import TurnTimer

logger = logging.getLogger(__name__)

# Query syntax that can't be a single tag: booleans, wildcards, fuzzy matches.
_OPERATOR_CHARS = set('|&()*~"')

# Payload types that show up in the client's guess feed. These are retained per
# round so a (re)joining client can replay the feed instead of starting blank;
# everything else in the stream is derivable from the snapshot's counts.
_FEED_TYPES = frozenset(
    {
        "correct_guess",
        "wrong_guess",
        "near_miss",
        "timeout",
        "guess_rejected",
        "player_eliminated",
    }
)


def _is_plain_tag(term: str) -> bool:
    """Whether a query term could be one tag, and so is worth an alias lookup.

    Conservative on purpose: a false negative leaves a freebie unresolved, while
    a false positive costs one lookup that finds nothing and is then cached.
    """
    if not term or term[0] in "-!" or _OPERATOR_CHARS & set(term):
        return False
    field, sep, _ = term.partition(":")
    return not (sep and "." in field)  # score.gte:100 filters; artist:x is a tag


class GameService:
    def __init__(
        self,
        image_source: ImageSource | None = None,
        emitter: EventEmitter | None = None,
        *,
        sources: Mapping[str, SourceBundle] | None = None,
        default_source: str = "derpibooru",
        tag_resolver: TagResolver | None = None,
        turn_seconds: float | None = None,
        max_query_lookups: int | None = None,
        game_options: dict | None = None,
    ):
        assert emitter is not None, "GameService needs an emitter"
        self._emitter = emitter
        self._default_source = default_source
        self._game_options = dict(game_options or {})
        # Taxonomy is per-source now, carried on the bundle rather than shared —
        # so lift it out of the common game options either way.
        fallback_taxonomy = self._game_options.pop("taxonomy", None)
        # A room selects a source by name; the bundle carries its provider,
        # resolver, and taxonomy. The single-source form (image_source=...) wraps
        # the one provider as the default bundle so existing callers and tests
        # keep working.
        if sources is not None:
            self._sources: dict[str, SourceBundle] = dict(sources)
        else:
            self._sources = {
                default_source: SourceBundle(
                    image_source=image_source,
                    tag_resolver=tag_resolver or NullTagResolver(),
                    taxonomy=fallback_taxonomy,
                )
            }
        self._turn_seconds = RoomDefaults().turn_seconds if turn_seconds is None else turn_seconds
        self._max_query_lookups = (
            LimitsSettings().max_query_lookups if max_query_lookups is None else max_query_lookups
        )
        self._timers: dict[str, TurnTimer] = {}
        self._current_image: dict[str, Image] = {}  # image on display, per room
        self._history: dict[str, list[dict]] = {}  # finished rounds, per room
        self._feed: dict[str, list[dict]] = {}  # current round's feed, per room
        self._starting: set[str] = set()  # rooms with an in-flight start

    def _bundle(self, room: Room) -> SourceBundle:
        """The source bundle a room pulls from; a stale/unknown key degrades to
        the default source rather than failing the round."""
        return self._sources.get(room.source, self._sources[self._default_source])

    async def start_game(
        self,
        room: Room,
        *,
        taxonomy: TagTaxonomy | None = None,
        first_index: int | None = None,
    ) -> None:
        """Fetch an image, open a game for the room's ready players, announce it."""
        if room.active or room.name in self._starting:
            return  # a game is already running, or a concurrent start is in flight
        # Reserve the room *before* the fetch await: the guard above only clears
        # once the game exists, so without this a second start slipping in during
        # the fetch would open a rival round. Set synchronously so the rival sees it.
        self._starting.add(room.name)
        bundle = self._bundle(room)
        try:
            try:
                image = await bundle.image_source.random_image(
                    room.query, options=_search_options(room)
                )
            except ImageSourceError as exc:
                logger.warning("Image fetch failed for room %r: %s", room.name, exc)
                await self._emitter.emit(room.name, [{"type": "image_error"}])
                return
            if image is None:
                logger.info("No image for room %r matching query %s", room.name, room.query)
                await self._emitter.emit(
                    room.name, [{"type": "no_image", "query": list(room.query)}]
                )
                return

            options = dict(self._game_options)
            # The room's source decides how tags are classified; an explicit
            # taxonomy= argument (tests) still wins over it.
            if bundle.taxonomy is not None:
                options["taxonomy"] = bundle.taxonomy
            if taxonomy is not None:
                options["taxonomy"] = taxonomy
            query = await self._canonical_query(bundle.tag_resolver, room.query, image.tags)
            game = room.start_game(image.tags, first_index=first_index, query=query, **options)
            logger.info("Game started in room %r (%d players)", room.name, len(game.players))
            self._current_image[room.name] = image
            self._feed[room.name] = []  # a new round starts from an empty feed
            await self._deliver(
                room, game.start(), lead=[_image_started_payload(image, room.source)]
            )
        finally:
            self._starting.discard(room.name)

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
        # The raw guess is kept so the events can report what the player actually
        # typed alongside the tag it resolved to.
        canonical = await self._canonicalized(self._bundle(room).tag_resolver, game, guess)
        await self._deliver(room, game.submit_guess(user_uuid, canonical, as_typed=guess))

    async def _canonicalized(self, resolver: TagResolver, game, guess: str) -> str:
        """Map an unrecognized guess to its canonical tag; leave known ones alone.

        A guess the game already recognizes needs no external help, so only novel
        strings (aliases, typos) reach the resolver — which returns them unchanged
        when there's no alias or the lookup can't be made.
        """
        if game.recognizes(guess):
            return guess
        return await resolver.canonicalize(guess)

    async def _canonical_query(
        self, resolver: TagResolver, query: list[str], tags: list[str]
    ) -> list[str]:
        """Resolve the query's plain tags so an aliased term still frees its tag.

        A term already on the image needs no lookup — the source stores canonical
        tags only, so it's canonical by definition. That leaves only the terms
        that could be aliases, capped at ``max_query_lookups``. Resolution is
        deliberately serial: the resolver stops hitting the network once it owes
        the source a back-off, so a serial pass self-limits after a failure where
        a concurrent one would empty the whole budget into it. Anything left
        literal just means a freebie goes unrecognized.
        """
        known = {tag.lower() for tag in tags}
        budget = self._max_query_lookups
        resolved = []
        for term in query:
            if term.lower() not in known and budget and _is_plain_tag(term):
                budget -= 1
                term = await resolver.canonicalize(term)
            resolved.append(term)
        return resolved

    async def handle_timeout(self, room: Room) -> None:
        """The active turn ran out of time. Invoked by the turn timer."""
        game = room.game
        if game is None or game.is_over:
            return
        await self._deliver(room, game.timeout())

    async def stop_game(self, room: Room, caller_uuid: str) -> None:
        """Abort the in-progress game and return the room to the lobby.

        Only a current, non-eliminated player may abort — no rage-quitting the
        round out from under everyone still in it. An aborted round still reveals
        the image (licensing + so a dropped image can still be tracked down),
        unlike an emptied room, which has no one left to reveal to.
        """
        if not room.active:
            return
        game = room.game  # read the answer key before end_game() discards it
        if game is not None and not game.has_active_player(caller_uuid):
            raise GameActionError("not_a_player")
        logger.info("Game aborted in room %r by %s", room.name, caller_uuid)
        self._drop_timer(room.name)
        unguessed = game.unguessed if game else {}
        room.end_game()
        room.clear_ready()  # aborting returns everyone to an unready lobby
        payloads: list[dict] = [{"type": "game_aborted", "unguessed": unguessed}]
        self._feed.pop(room.name, None)
        image = self._current_image.pop(room.name, None)
        if image is not None:
            payloads.append(_image_revealed_payload(image))
            self._record_round(room, image, None)  # aborted: no result
        await self._emitter.emit(room.name, payloads)

    def rating_axes_for(self, room: Room) -> list[dict]:
        """A room's source rating scales, for cap validation and the lobby UI."""
        return [
            {
                "key": axis.key,
                "label": axis.label,
                "levels": [step.name for step in axis.levels],
            }
            for axis in self._bundle(room).image_source.rating_axes
        ]

    @property
    def available_sources(self) -> list[dict]:
        """The image providers a room may pick, for the lobby picker."""
        return [{"key": key, "label": key.capitalize()} for key in self._sources]

    def knows_source(self, key: str) -> bool:
        """Whether ``key`` names a configured source (rejects unknown selections)."""
        return key in self._sources

    def turn_seconds_for(self, room: Room) -> float:
        """The room's turn length, falling back to the deployment default."""
        return room.turn_seconds if room.turn_seconds is not None else self._turn_seconds

    async def _deliver(self, room: Room, events: list, *, lead: list[dict] | None = None) -> None:
        payloads = list(lead or []) + serialize_events(events)
        for payload in payloads:
            if payload["type"] == "game_started":
                payload["turn_seconds"] = self.turn_seconds_for(room)
        self._record_feed(room.name, payloads)
        game_over = next((e for e in events if isinstance(e, GameOver)), None)
        if game_over is not None:
            image = self._current_image.pop(room.name, None)
            if image is not None:
                payloads.append(_image_revealed_payload(image))
                self._record_round(room, image, game_over)
            room.clear_ready()  # round's done — the next needs a fresh ready-up
        try:
            if payloads:
                await self._emitter.emit(room.name, payloads)
        except Exception:
            logger.exception("Failed to emit game events for room %r", room.name)
            raise
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

    def _record_feed(self, room_name: str, payloads: list[dict]) -> None:
        """Keep the round's feed-worthy payloads for later replay into a snapshot."""
        feed = self._feed.get(room_name)
        if feed is None:
            return
        feed.extend(p for p in payloads if p["type"] in _FEED_TYPES)

    def _drop_timer(self, room_name: str) -> None:
        timer = self._timers.pop(room_name, None)
        if timer is not None:
            timer.cancel()

    def _record_round(self, room: Room, image: Image, game_over: GameOver | None) -> None:
        """Append a finished round to the room's history (game over or abort)."""
        record = _round_record(image, game_over, nsfw=room.nsfw, source=room.source)
        self._history.setdefault(room.name, []).append(record)

    def room_history(self, room_name: str) -> list[dict]:
        """The room's finished rounds, oldest first — for the lobby snapshot."""
        return list(self._history.get(room_name, ()))

    def room_win_counts(self, room_name: str) -> list[dict]:
        """Wins per player across the room's finished rounds, most first."""
        return _tally_wins(self._history.get(room_name, ()))

    def game_snapshot(self, room: Room) -> dict | None:
        """An answer-safe view of the in-progress game for a (re)joining client.

        Carries the current image, roster with scores, whose turn it is, the
        freebie tags, remaining counts, the round's feed so far, and what's left
        of the active turn — never the unguessed goal tags. ``None`` when no game
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
            "source": room.source,
            "players": [serialize_player(p) for p in (*game.players, *game.eliminated_players)],
            "active_player": serialize_player(game.active_player),
            "freebie_tags": list(game.freebie_tags),
            "tag_count": goal_remaining + goal_guessed,  # original goal-bucket size
            "goal_remaining": goal_remaining,
            "bonus_counts": {
                key: bucket.tag_count for key, bucket in game.tag_buckets.items() if key != goal_key
            },
            "eliminated": [p.uuid for p in game.eliminated_players],
            "turn_seconds": self.turn_seconds_for(room),
            "elimination_threshold": game.elimination_threshold,
            "turn_remaining": self._turn_remaining(room),
            "feed": list(self._feed.get(room.name, ())),
        }

    def _turn_remaining(self, room: Room) -> float:
        """Seconds left on the active turn, so a rejoining clock resumes mid-turn."""
        timer = self._timers.get(room.name)
        remaining = timer.remaining if timer is not None else None
        return remaining if remaining is not None else self.turn_seconds_for(room)

    def cancel_room(self, room_name: str) -> None:
        """Release a room's turn timer, image, feed, and history when it's torn down."""
        self._drop_timer(room_name)
        self._current_image.pop(room_name, None)
        self._history.pop(room_name, None)
        self._feed.pop(room_name, None)

    def shutdown(self) -> None:
        """Cancel every pending turn timer (app shutdown, or test cleanup)."""
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        self._current_image.clear()
        self._history.clear()
        self._feed.clear()
        self._starting.clear()


def _search_options(room: Room) -> SearchOptions:
    """Map a room's search config onto a provider-agnostic query spec."""
    return SearchOptions(
        nsfw=room.nsfw,
        min_tag_count=room.min_tag_count,
        min_score=room.min_score,
        rating_caps=dict(room.rating_caps),
    )


def _image_started_payload(image: Image, source: str) -> dict:
    """The picture to display — deliberately without any answer-revealing tags.

    ``source`` pins the round to the booru it came from, so the end-of-round tag
    links stay correct even if the room switches source while the results are up.
    """
    return {
        "type": "image_started",
        "id": image.id,
        "thumb_url": image.thumb_url,
        "full_url": image.full_url,
        "source": source,
    }


_ARTIST_PREFIX = "artist:"


def _artist_names(image: Image) -> list[str]:
    return [tag[len(_ARTIST_PREFIX) :] for tag in image.tags if tag.startswith(_ARTIST_PREFIX)]


def _image_revealed_payload(image: Image) -> dict:
    """Attribution shown once the image is no longer a secret (game end/abort)."""
    return {
        "type": "image_revealed",
        "artists": _artist_names(image),
        "source_url": image.source_url,
        "page_url": image.page_url,
    }


def _round_record(image: Image, game_over: GameOver | None, *, nsfw: bool, source: str) -> dict:
    """A finished round for the history: its link/attribution plus the result.

    ``game_over is None`` means the round was aborted — it has a link worth
    keeping but no winners or final standings. ``nsfw`` is the room's setting
    when the round was played, so its thumbnail stays gated even if the room is
    later switched to SFW. ``source`` is which booru it came from, so the
    history's tag links point at the right site.
    """
    return {
        "page_url": image.page_url,
        "source_url": image.source_url,
        "thumb_url": image.thumb_url,
        "nsfw": nsfw,
        "source": source,
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
