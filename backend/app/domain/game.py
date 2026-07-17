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

RATING_TAGS = frozenset(
    {
        "explicit",
        "grimdark",
        "grotesque",
        "questionable",
        "safe",
        "semi-grimdark",
        "suggestive",
    }
)


class Game:
    ELIMINATION_THRESHOLD = 3
    SIMILARITY_THRESHOLD = 0.7

    def __init__(
        self,
        players: list[Player],
        tags: list[str],
        query: list[str],
        first_index: int | None = None,
        elimination_threshold: int | None = None,
        similarity_threshold: float | None = None,
    ):
        if not players:
            raise ValueError("a game needs at least one player")
        self.players = list(players)
        self.eliminated_players: list[Player] = []
        self.query = [tag.lower() for tag in query]
        self.guessed_tags: list[str] = []
        self.incorrect_guesses: list[tuple[str, int]] = []  # (guess, closeness %)
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
        artists = [t for t in tags if t.startswith("artist:") and t not in query]
        ocs = [t for t in tags if t.startswith("oc:") and t not in query]
        special = set(artists) | set(ocs)
        regular = [
            t
            for t in tags
            if t not in special
            and t not in query
            and not t.startswith("spoiler:")
            and t not in RATING_TAGS
        ]
        return {
            "tags": TagBucket(regular),
            "artists": TagBucket(artists),
            "ocs": TagBucket(ocs),
        }

    @property
    def active_player(self) -> Player:
        return self.players[self._active_index]

    @property
    def is_over(self) -> bool:
        return self._finished

    def start(self) -> list[GameEvent]:
        """Announce the opening: tag counts and whose turn it is."""
        first = self.active_player
        return [
            GameStarted(
                first_player=first,
                tag_count=self.tag_buckets["tags"].tag_count,
                artist_count=self.tag_buckets["artists"].tag_count,
                oc_count=self.tag_buckets["ocs"].tag_count,
                query=list(self.query),
            ),
            TurnStarted(first),
        ]

    def submit_guess(self, guess: str) -> list[GameEvent]:
        """Process the active player's guess and return what happened.

        Rejected guesses (already guessed, default query tags, rating tags) are
        no-ops: the player keeps their turn. Correct and wrong guesses both end
        the turn and advance the game. Guesses after the game is over are ignored.
        """
        if self._finished:
            return []
        guess = guess.lower()

        if guess in self.guessed_tags:
            return [GuessRejected(guess, RejectReason.ALREADY_GUESSED)]
        if guess in self.query:
            return [GuessRejected(guess, RejectReason.DEFAULT_TAG)]
        if guess in RATING_TAGS:
            return [GuessRejected(guess, RejectReason.RATING_TAG)]

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
        closeness = self._closeness(guess)
        self.incorrect_guesses.append((guess, closeness))
        return WrongGuess(player, guess, player.wrong_guesses, closeness)

    def _closeness(self, guess: str) -> int:
        """Best fuzzy match of ``guess`` against the relevant bucket, as a %.

        Returns 0 when nothing clears the similarity threshold. ``oc:`` and
        ``artist:`` guesses are matched against their own buckets with the
        prefix stripped so the namespace doesn't dominate the ratio.
        """
        if guess.startswith("oc:"):
            needle, candidates = guess[3:], [t[3:] for t in self.tag_buckets["ocs"].tags]
        elif guess.startswith("artist:"):
            needle, candidates = guess[7:], [t[7:] for t in self.tag_buckets["artists"].tags]
        else:
            needle, candidates = guess, self.tag_buckets["tags"].tags

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

        if self.tag_buckets["tags"].tag_count == 0:
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
        top = standings[0].score
        winners = [p for p in standings if p.score == top]
        return GameOver(
            win=win,
            winners=winners,
            standings=standings,
            unguessed_tags=list(self.tag_buckets["tags"].tags),
        )
