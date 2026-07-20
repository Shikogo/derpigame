"""Core game rules: turn rotation, guessing, scoring, elimination, endgame.

A game is driven by three inputs — ``submit_guess``, ``timeout``, and the
initial ``start`` — each of which mutates state and returns a list of
``GameEvent`` objects describing what happened. Nothing here emits, renders, or
talks to a framework; translating events into messages is the caller's job.
"""

from difflib import SequenceMatcher
from random import randrange

from .events import (
    CorrectGuess,
    GameEvent,
    GameOver,
    GameStarted,
    GuessRejected,
    NearMiss,
    PlayerEliminated,
    RejectReason,
    Timeout,
    TurnStarted,
    WrongGuess,
)
from .player import Player
from .tag_bucket import TagBucket
from .tag_taxonomy import DERPIBOORU_TAXONOMY, TagTaxonomy


class Game:
    ELIMINATION_THRESHOLD = 3
    NEAR_MISS_THRESHOLD = 0.85  # ratio; at/above this a guess is a free retry

    def __init__(
        self,
        players: list[Player],
        tags: list[str],
        query: list[str],
        first_index: int | None = None,
        taxonomy: TagTaxonomy | None = None,
        elimination_threshold: int | None = None,
        near_miss_threshold: float | None = None,
    ):
        if not players:
            raise ValueError("a game needs at least one player")
        self.players = list(players)
        self.eliminated_players: list[Player] = []
        self.taxonomy = taxonomy or DERPIBOORU_TAXONOMY
        self.query = [tag.lower() for tag in query]
        self.guessed_tags: list[str] = []
        self.failed_guesses: set[str] = set()  # guesses already tried and known wrong
        self.freebie_tags: list[str] = []  # filled by _bucket_tags
        self._started = False
        self._finished = False
        self.tag_buckets = self._bucket_tags([tag.lower() for tag in tags])
        self._bare_names = self._index_bare_names()
        self._active_index = randrange(len(self.players)) if first_index is None else first_index
        self.elimination_threshold = (
            self.ELIMINATION_THRESHOLD if elimination_threshold is None else elimination_threshold
        )
        self.near_miss_threshold = (
            self.NEAR_MISS_THRESHOLD if near_miss_threshold is None else near_miss_threshold
        )

    def _bucket_tags(self, tags: list[str]) -> dict[str, TagBucket]:
        """Sort the image's tags into buckets, setting aside the query's freebies.

        A tag the query already named is recorded as a freebie rather than
        bucketed — it's known before the round starts, so it can't be scored.
        """
        query = set(self.query)
        keys = [self.taxonomy.goal_bucket, *self.taxonomy.namespaces]
        buckets: dict[str, list[str]] = {key: [] for key in keys}
        for tag in tags:
            if tag in query:
                self.freebie_tags.append(tag)
                continue
            if self.taxonomy.is_droppable(tag):
                continue
            buckets[self.taxonomy.bucket_for(tag)].append(tag)
        return {key: TagBucket(tags) for key, tags in buckets.items()}

    def _index_bare_names(self) -> dict[str, str]:
        """Map each namespaced tag's bare name to the tag itself.

        Lets a player score ``shikogo`` for ``artist:shikogo``: the prefix is
        booru schema literacy, not something you read off the picture. A bare
        name that's already a plain tag, a query term, or a reserved word is
        left out — a plain tag gates the win and a rating is meant to be
        refused, so neither can lose the collision to an artist who happens to
        share the name. Between two namespaces the first in taxonomy order wins.
        """
        taken = (
            set(self._goal_bucket.tags)
            | set(self.query)
            | self.taxonomy.rating_tags
            | self.taxonomy.ignored_tags
        )
        goal = self.taxonomy.goal_bucket
        index: dict[str, str] = {}
        for key, bucket in self.tag_buckets.items():
            if key == goal:
                continue
            for tag in bucket.tags:
                bare = self.taxonomy.bare(tag)
                if bare not in taken:
                    index.setdefault(bare, tag)
        return index

    def _resolve(self, guess: str) -> str:
        """A bare name expanded to the namespaced tag it names, else unchanged.

        Applied before anything else looks at a guess, so the rest of the game
        only ever handles canonical tags — which is what makes "already
        guessed" and the reported ``tag_type`` fall out without special cases.
        """
        return self._bare_names.get(guess, guess)

    @property
    def _goal_bucket(self) -> TagBucket:
        return self.tag_buckets[self.taxonomy.goal_bucket]

    @property
    def unguessed(self) -> dict[str, list[str]]:
        """Tags nobody got, goal bucket first; empty buckets omitted.

        Buckets only ever hold what's left, so this is the answer key for a
        round that's ending — never expose it while one is still running.
        """
        return {key: list(b.tags) for key, b in self.tag_buckets.items() if b.tags}

    @property
    def active_player(self) -> Player:
        return self.players[self._active_index]

    @property
    def is_over(self) -> bool:
        return self._finished

    def start(self) -> list[GameEvent]:
        """Announce the opening: tag counts and whose turn it is.

        Idempotent — starting an already-started or finished game is a no-op, so
        a stray re-start can't re-announce the opening or reset the turn.
        """
        if self._started or self._finished:
            return []
        self._started = True
        first = self.active_player
        goal = self.taxonomy.goal_bucket
        return [
            GameStarted(
                first_player=first,
                tag_count=self._goal_bucket.tag_count,
                bonus_counts={
                    key: bucket.tag_count for key, bucket in self.tag_buckets.items() if key != goal
                },
                freebie_tags=list(self.freebie_tags),
                players=list(self.players),
            ),
            TurnStarted(first),
        ]

    def recognizes(self, guess: str) -> bool:
        """Whether ``submit_guess`` already has a verdict for ``guess`` as-is.

        True when the guess is a known tag (in a bucket) or hits one of that
        method's early returns (already found/wrong, default/rating/ignored). An
        unrecognized guess is the only kind worth resolving through an alias
        lookup — everything else needs no external help.
        """
        guess = self._resolve(guess.lower())
        if guess in self.guessed_tags or guess in self.failed_guesses:
            return True
        if guess in self.query:
            return True
        if guess in self.taxonomy.rating_tags or guess in self.taxonomy.ignored_tags:
            return True
        return any(guess in bucket.tags for bucket in self.tag_buckets.values())

    def submit_guess(self, guess: str) -> list[GameEvent]:
        """Process the active player's guess and return what happened.

        Rejected guesses (already found, already tried and wrong, default query
        tags, rating tags, ignored tags) are no-ops: the player keeps their turn
        and takes no penalty. A very close near-miss (similarity >=
        NEAR_MISS_THRESHOLD) is treated the same — no penalty, retry allowed.
        Correct and fresh wrong guesses both end the turn and advance the game.
        Guesses after the game is over are ignored.

        A bare ``shikogo`` is resolved to ``artist:shikogo`` first, so the events
        report the canonical tag and the feed shows the prefix back.
        """
        if self._finished:
            return []
        guess = self._resolve(guess.lower())

        if guess in self.guessed_tags:
            return [GuessRejected(guess, RejectReason.ALREADY_GUESSED)]
        if guess in self.failed_guesses:
            return [GuessRejected(guess, RejectReason.ALREADY_WRONG)]
        if guess in self.query:
            return [GuessRejected(guess, RejectReason.DEFAULT_TAG)]
        if guess in self.taxonomy.rating_tags:
            return [GuessRejected(guess, RejectReason.RATING_TAG)]
        if guess in self.taxonomy.ignored_tags:
            return [GuessRejected(guess, RejectReason.IGNORED_TAG)]

        for kind, bucket in self.tag_buckets.items():
            if bucket.take(guess):
                self.active_player.score += 1
                self.guessed_tags.append(guess)
                correct = CorrectGuess(
                    player=self.active_player,
                    guess=guess,
                    tag_type=kind,
                    remaining=bucket.tag_count,
                )
                return [correct, *self._progress()]

        similarity = self._similarity(guess)
        if similarity >= self.near_miss_threshold:
            closeness = round(similarity * 100)  # percent, for display
            return [NearMiss(self.active_player, guess, closeness)]
        return [self._wrong_guess(guess), *self._progress()]

    def timeout(self) -> list[GameEvent]:
        """The active player ran out of time — counts as a wrong guess."""
        if self._finished:
            return []
        player = self.active_player
        player.wrong_guesses += 1
        return [Timeout(player, player.wrong_guesses), *self._progress()]

    def _wrong_guess(self, guess: str) -> WrongGuess:
        player = self.active_player
        player.wrong_guesses += 1
        self.failed_guesses.add(guess)
        return WrongGuess(player, guess, player.wrong_guesses)

    def _similarity(self, guess: str) -> float:
        """Best fuzzy match of ``guess`` against the relevant bucket, as a ratio.

        Returns 0.0 when nothing reaches the near-miss threshold. A namespaced
        guess is matched against its own bucket with the prefix stripped, so the
        shared namespace doesn't inflate the ratio.
        """
        bucket_key = self.taxonomy.bucket_for(guess)
        needle = self.taxonomy.bare(guess)
        candidates = [self.taxonomy.bare(tag) for tag in self.tag_buckets[bucket_key].tags]

        best = 0.0
        for candidate in candidates:
            matcher = SequenceMatcher(None, needle, candidate)
            if matcher.quick_ratio() >= self.near_miss_threshold:
                best = max(best, matcher.ratio())

        return best if best >= self.near_miss_threshold else 0.0

    def _progress(self) -> list[GameEvent]:
        """Advance the game after a turn-ending guess or timeout."""
        if self.active_player.wrong_guesses >= self.elimination_threshold:
            eliminated = self.players.pop(self._active_index)
            self.eliminated_players.append(eliminated)
            events: list[GameEvent] = [PlayerEliminated(eliminated)]
            if not self.players:
                return [*events, self._game_over(win=False)]
            if self._active_index >= len(self.players):
                self._active_index = 0
            return [*events, TurnStarted(self.active_player)]

        if self._goal_bucket.tag_count == 0:
            return [self._game_over(win=True)]

        self._active_index = (self._active_index + 1) % len(self.players)
        return [TurnStarted(self.active_player)]

    def _game_over(self, win: bool) -> GameOver:
        self._finished = True
        standings = sorted(
            self.players + self.eliminated_players,
            key=lambda p: p.score,
            reverse=True,
        )
        # Winner = the top scorer(s), whether the goal was completed or everyone
        # got eliminated first. No crown for a solo elimination (no one to
        # out-score) or a round where nobody scored at all.
        top = standings[0].score
        winners = (
            [p for p in standings if p.score == top]
            if top > 0 and (win or len(standings) > 1)
            else []
        )
        return GameOver(
            win=win,
            winners=winners,
            standings=standings,
            unguessed=self.unguessed,
        )
