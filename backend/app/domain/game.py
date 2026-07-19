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
    SIMILARITY_THRESHOLD = 0.7

    def __init__(
        self,
        players: list[Player],
        tags: list[str],
        query: list[str],
        first_index: int | None = None,
        taxonomy: TagTaxonomy | None = None,
        elimination_threshold: int | None = None,
        similarity_threshold: float | None = None,
    ):
        if not players:
            raise ValueError("a game needs at least one player")
        self.players = list(players)
        self.eliminated_players: list[Player] = []
        self.taxonomy = taxonomy or DERPIBOORU_TAXONOMY
        self.query = [tag.lower() for tag in query]
        self.guessed_tags: list[str] = []
        self.failed_guesses: set[str] = set()  # guesses already tried and known wrong
        self._started = False
        self._finished = False
        self.tag_buckets = self._bucket_tags([tag.lower() for tag in tags])
        self._active_index = (
            randrange(len(self.players)) if first_index is None else first_index
        )
        self.elimination_threshold = (
            self.ELIMINATION_THRESHOLD
            if elimination_threshold is None
            else elimination_threshold
        )
        self.similarity_threshold = (
            self.SIMILARITY_THRESHOLD
            if similarity_threshold is None
            else similarity_threshold
        )

    def _bucket_tags(self, tags: list[str]) -> dict[str, TagBucket]:
        query = set(self.query)
        keys = [self.taxonomy.goal_bucket, *self.taxonomy.namespaces]
        buckets: dict[str, list[str]] = {key: [] for key in keys}
        for tag in tags:
            if tag in query or self.taxonomy.is_droppable(tag):
                continue
            buckets[self.taxonomy.bucket_for(tag)].append(tag)
        return {key: TagBucket(tags) for key, tags in buckets.items()}

    @property
    def _goal_bucket(self) -> TagBucket:
        return self.tag_buckets[self.taxonomy.goal_bucket]

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
                    key: bucket.tag_count
                    for key, bucket in self.tag_buckets.items()
                    if key != goal
                },
                query=list(self.query),
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
        guess = guess.lower()
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
        and takes no penalty. Correct and fresh wrong guesses both end the turn
        and advance the game. Guesses after the game is over are ignored.
        """
        if self._finished:
            return []
        guess = guess.lower()

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
        return WrongGuess(player, guess, player.wrong_guesses, self._closeness(guess))

    def _closeness(self, guess: str) -> int:
        """Best fuzzy match of ``guess`` against the relevant bucket, as a %.

        Returns 0 when nothing clears the similarity threshold. A namespaced
        guess is matched against its own bucket with the prefix stripped, so the
        shared namespace doesn't inflate the ratio.
        """
        bucket_key = self.taxonomy.bucket_for(guess)
        prefix = self.taxonomy.prefix_of(bucket_key)
        needle = guess[len(prefix):]
        candidates = [tag[len(prefix):] for tag in self.tag_buckets[bucket_key].tags]

        best = 0.0
        for candidate in candidates:
            matcher = SequenceMatcher(None, needle, candidate)
            if matcher.quick_ratio() >= self.similarity_threshold:
                best = max(best, matcher.ratio())

        return round(best * 100) if best >= self.similarity_threshold else 0

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
            unguessed_tags=list(self._goal_bucket.tags),
        )
