"""Domain rules for Game — turn order, scoring, elimination, endgame.

These run with no framework or app context: build a Game, drive it with
guesses/timeouts, and assert on the returned event objects and state.
"""

import pytest

from app.domain.events import (
    CorrectGuess,
    GameOver,
    GameStarted,
    GuessRejected,
    PlayerEliminated,
    RejectReason,
    Timeout,
    TurnStarted,
    WrongGuess,
)
from app.domain.game import Game
from app.domain.player import Player
from app.domain.tag_taxonomy import TagTaxonomy
from app.domain.user import User


def make_players(*names: str) -> list[Player]:
    return [Player(User(uuid=name, name=name)) for name in names]


def make_game(
    tags: list[str],
    players: list[str] | None = None,
    query: list[str] | None = None,
    first_index: int = 0,
    **kwargs,
) -> Game:
    return Game(
        players=make_players(*(players or ["alice", "bob"])),
        tags=tags,
        query=query or [],
        first_index=first_index,
        **kwargs,
    )


def only(events, event_type):
    """Return the single event of the given type, asserting there's exactly one."""
    matches = [e for e in events if isinstance(e, event_type)]
    assert len(matches) == 1, f"expected one {event_type.__name__}, got {matches}"
    return matches[0]


# --- setup / bucketing -------------------------------------------------------


def test_tags_are_bucketed_by_kind():
    game = make_game(
        tags=["solo", "artist:foo", "oc:bar", "spoiler:reveal", "safe"],
        query=["cute"],
    )
    assert game.tag_buckets["tags"].tags == ["solo"]
    assert game.tag_buckets["artists"].tags == ["artist:foo"]
    assert game.tag_buckets["ocs"].tags == ["oc:bar"]


def test_query_and_rating_tags_are_excluded_from_buckets():
    game = make_game(tags=["solo", "safe", "cute"], query=["cute"])
    assert game.tag_buckets["tags"].tags == ["solo"]


def test_start_reports_counts_and_first_player():
    game = make_game(
        tags=["solo", "twilight", "artist:foo", "oc:bar"], first_index=1
    )
    events = game.start()
    started = only(events, GameStarted)
    assert started.first_player is game.players[1]
    assert started.tag_count == 2
    assert started.bonus_counts == {"artists": 1, "ocs": 1}
    assert only(events, TurnStarted).player is game.players[1]


def test_start_is_idempotent():
    game = make_game(tags=["solo", "twilight"], first_index=0)
    assert game.start()  # first start announces the opening
    assert game.submit_guess("solo")  # advance turn to bob
    assert game.start() == []  # a stray re-start is a no-op
    assert game.active_player.name == "bob"  # turn state untouched


# --- rejected guesses are no-ops (do not advance the turn) -------------------


def test_already_guessed_tag_is_noop_and_keeps_turn():
    game = make_game(tags=["solo", "twilight"], first_index=0)
    game.submit_guess("solo")  # alice scores, turn passes to bob
    assert game.active_player.name == "bob"

    events = game.submit_guess("solo")  # bob re-guesses an already-found tag
    rejected = only(events, GuessRejected)
    assert rejected.reason is RejectReason.ALREADY_GUESSED
    assert not any(isinstance(e, TurnStarted) for e in events)
    assert game.active_player.name == "bob"  # still bob's turn
    assert game.active_player.wrong_guesses == 0  # no penalty


def test_default_query_tag_is_rejected_without_penalty():
    game = make_game(tags=["solo"], query=["cute"], first_index=0)
    events = game.submit_guess("cute")
    assert only(events, GuessRejected).reason is RejectReason.DEFAULT_TAG
    assert game.active_player.name == "alice"
    assert game.active_player.wrong_guesses == 0


def test_rating_tag_is_rejected_without_penalty():
    game = make_game(tags=["solo"], first_index=0)
    events = game.submit_guess("safe")
    assert only(events, GuessRejected).reason is RejectReason.RATING_TAG
    assert game.active_player.wrong_guesses == 0


def test_repeated_wrong_guess_is_noop_without_extra_penalty():
    game = make_game(tags=["solo"], players=["alice", "bob"], first_index=0)
    game.submit_guess("nope")  # alice's 1st wrong -> turn passes to bob
    assert game.active_player.name == "bob"

    events = game.submit_guess("nope")  # bob re-tries a known-wrong guess
    assert only(events, GuessRejected).reason is RejectReason.ALREADY_WRONG
    assert not any(isinstance(e, TurnStarted) for e in events)
    assert game.active_player.name == "bob"  # keeps the turn
    assert game.active_player.wrong_guesses == 0  # no strike for the repeat


# --- correct guesses ---------------------------------------------------------


def test_correct_guess_scores_removes_tag_and_advances_turn():
    game = make_game(tags=["solo", "twilight"], first_index=0)
    events = game.submit_guess("SOLO")  # case-insensitive

    correct = only(events, CorrectGuess)
    assert correct.player.name == "alice"
    assert correct.tag_type == "tags"
    assert correct.remaining == 1
    assert game.players[0].score == 1
    assert "solo" not in game.tag_buckets["tags"].tags
    assert only(events, TurnStarted).player.name == "bob"


def test_correct_artist_guess_reports_artist_bucket():
    game = make_game(tags=["solo", "artist:foo"], first_index=0)
    events = game.submit_guess("artist:foo")
    assert only(events, CorrectGuess).tag_type == "artists"


# --- wrong guesses & near misses --------------------------------------------


def test_wrong_guess_increments_count_and_advances_turn():
    game = make_game(tags=["solo"], first_index=0)
    events = game.submit_guess("nonsense")

    wrong = only(events, WrongGuess)
    assert wrong.player.name == "alice"
    assert wrong.wrong_count == 1
    assert wrong.closeness == 0
    assert only(events, TurnStarted).player.name == "bob"


def test_near_miss_reports_closeness():
    game = make_game(tags=["applejack"], first_index=0)
    wrong = only(game.submit_guess("applejck"), WrongGuess)
    assert wrong.closeness > 0


def test_unrelated_guess_has_zero_closeness():
    game = make_game(tags=["applejack"], first_index=0)
    wrong = only(game.submit_guess("xyz"), WrongGuess)
    assert wrong.closeness == 0


# --- elimination -------------------------------------------------------------


def test_three_wrong_guesses_eliminates_player():
    game = make_game(tags=["solo", "twilight"], players=["alice", "bob"], first_index=0)
    game.submit_guess("wrong1")  # alice 1st wrong -> bob
    game.submit_guess("wrong2")  # bob 1st wrong -> alice
    game.submit_guess("wrong3")  # alice 2nd wrong -> bob
    game.submit_guess("wrong4")  # bob 2nd wrong -> alice
    events = game.submit_guess("wrong5")  # alice 3rd wrong -> eliminated

    eliminated = only(events, PlayerEliminated)
    assert eliminated.player.name == "alice"
    assert [p.name for p in game.players] == ["bob"]
    assert only(events, TurnStarted).player.name == "bob"


def test_elimination_reindexes_to_the_following_player():
    game = make_game(tags=["solo"], players=["a", "b", "c"], first_index=1)
    # distinct guesses each turn — repeats are no-ops and wouldn't accumulate
    for n in ("1", "2"):
        game.submit_guess("b" + n)  # b
        game.submit_guess("c" + n)  # c
        game.submit_guess("a" + n)  # a
    # b now at 2 wrong guesses and it's b's turn again
    assert game.active_player.name == "b"
    events = game.submit_guess("boom")  # b's 3rd wrong -> eliminated
    only(events, PlayerEliminated)
    assert [p.name for p in game.players] == ["a", "c"]
    assert only(events, TurnStarted).player.name == "c"


def test_elimination_of_last_index_wraps_to_first():
    game = make_game(tags=["solo"], players=["a", "b", "c"], first_index=2)
    for n in ("1", "2"):
        game.submit_guess("c" + n)  # c
        game.submit_guess("a" + n)  # a
        game.submit_guess("b" + n)  # b
    assert game.active_player.name == "c"
    events = game.submit_guess("boom")  # c's 3rd wrong -> eliminated, wrap to a
    only(events, PlayerEliminated)
    assert only(events, TurnStarted).player.name == "a"


def test_all_players_eliminated_ends_game_as_loss():
    game = make_game(tags=["solo"], players=["alice"], first_index=0)
    game.submit_guess("x")
    game.submit_guess("y")
    events = game.submit_guess("z")  # 3rd wrong, only player -> game over
    over = only(events, GameOver)
    assert over.win is False
    assert over.unguessed_tags == ["solo"]


# --- winning & ties ----------------------------------------------------------


def test_win_when_all_regular_tags_guessed():
    game = make_game(tags=["solo"], first_index=0)
    events = game.submit_guess("solo")
    over = only(events, GameOver)
    assert over.win is True
    assert over.unguessed_tags == []


def test_win_ignores_remaining_artist_and_oc_tags():
    game = make_game(tags=["solo", "artist:foo", "oc:bar"], first_index=0)
    events = game.submit_guess("solo")  # last regular tag
    over = only(events, GameOver)
    assert over.win is True
    assert game.tag_buckets["artists"].tag_count == 1
    assert game.tag_buckets["ocs"].tag_count == 1


def test_tie_detection_lists_all_top_scorers():
    game = make_game(tags=["aaa", "bbb"], players=["alice", "bob"], first_index=0)
    game.submit_guess("aaa")  # alice scores, turn -> bob
    events = game.submit_guess("bbb")  # bob scores, last tag -> win
    over = only(events, GameOver)
    assert over.win is True
    assert {p.name for p in over.winners} == {"alice", "bob"}


def test_single_winner_ranked_first_in_standings():
    game = make_game(tags=["aaa", "bbb"], players=["alice", "bob"], first_index=0)
    game.submit_guess("aaa")  # alice 1 point -> bob
    game.submit_guess("wrong")  # bob wrong -> alice
    events = game.submit_guess("bbb")  # alice 2nd point, last tag -> win
    over = only(events, GameOver)
    assert [p.name for p in over.winners] == ["alice"]
    assert over.standings[0].name == "alice"


# --- timeout -----------------------------------------------------------------


def test_timeout_counts_as_wrong_and_advances_turn():
    game = make_game(tags=["solo"], first_index=0)
    events = game.timeout()
    timed = only(events, Timeout)
    assert timed.player.name == "alice"
    assert timed.wrong_count == 1
    assert game.players[0].wrong_guesses == 1
    assert only(events, TurnStarted).player.name == "bob"


def test_timeout_can_eliminate():
    game = make_game(tags=["solo"], players=["alice"], first_index=0)
    game.timeout()
    game.timeout()
    events = game.timeout()  # 3rd -> eliminated, only player -> game over
    only(events, PlayerEliminated)
    assert only(events, GameOver).win is False


# --- config injection --------------------------------------------------------


def test_elimination_threshold_is_configurable():
    game = make_game(tags=["solo"], players=["alice"], first_index=0, elimination_threshold=1)
    events = game.submit_guess("wrong")  # 1 wrong is enough now
    only(events, PlayerEliminated)
    assert only(events, GameOver).win is False


# --- tag taxonomy (source-specific classification is injected) ---------------


def test_custom_taxonomy_buckets_by_its_own_namespaces():
    # An e621-flavoured scheme: different namespaces, ratings, and no spoilers.
    taxonomy = TagTaxonomy(
        namespaces={"artists": "artist:", "characters": "character:"},
        rating_tags=frozenset({"explicit"}),
    )
    game = make_game(
        tags=["fluffy", "artist:someone", "character:rex", "explicit"],
        taxonomy=taxonomy,
    )
    assert game.tag_buckets["tags"].tags == ["fluffy"]
    assert game.tag_buckets["characters"].tags == ["character:rex"]
    assert "ocs" not in game.tag_buckets  # derpibooru's namespace isn't present
    # its rating tag is dropped, and guessing it is rejected as a rating
    assert only(game.submit_guess("explicit"), GuessRejected).reason is RejectReason.RATING_TAG


def test_custom_taxonomy_reports_its_buckets_in_game_started():
    taxonomy = TagTaxonomy(namespaces={"characters": "character:"})
    game = make_game(tags=["fluffy", "character:rex"], taxonomy=taxonomy)
    started = only(game.start(), GameStarted)
    assert started.tag_count == 1
    assert started.bonus_counts == {"characters": 1}


# --- robustness: input normalization, empty players, post-game-over ----------


def test_uppercase_query_and_tags_are_normalized():
    game = make_game(tags=["Solo", "TWILIGHT"], query=["Cute"], first_index=0)
    assert game.tag_buckets["tags"].tags == ["solo", "twilight"]
    # a mixed-case default tag is still rejected, not treated as guessable
    assert only(game.submit_guess("CUTE"), GuessRejected).reason is RejectReason.DEFAULT_TAG


def test_empty_player_list_is_rejected():
    with pytest.raises(ValueError):
        Game(players=[], tags=["solo"], query=[])


def test_game_is_marked_over_and_ignores_further_input():
    game = make_game(tags=["solo"], first_index=0)
    game.submit_guess("solo")  # win
    assert game.is_over is True
    assert game.submit_guess("anything") == []
    assert game.timeout() == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
