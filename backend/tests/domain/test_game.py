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
    NearMiss,
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


def test_freebies_are_the_image_tags_the_query_named():
    game = make_game(tags=["solo", "safe", "cute"], query=["cute"])
    assert game.freebie_tags == ["cute"]
    assert game.start()[0].freebie_tags == ["cute"]


def test_a_query_term_that_is_not_a_tag_is_no_freebie():
    # Operators and range filters match no tag, so they free nothing.
    game = make_game(tags=["solo", "cute"], query=["cute", "-anthro", "score.gte:100", "a || b"])
    assert game.freebie_tags == ["cute"]
    assert game.tag_buckets["tags"].tags == ["solo"]


def test_ignored_tags_do_not_gate_a_win():
    # Unguessable source-link housekeeping shouldn't land in the goal bucket.
    game = make_game(tags=["solo", "source needed", "dead source"], first_index=0)
    assert game.tag_buckets["tags"].tags == ["solo"]
    events = game.start()
    assert only(events, GameStarted).tag_count == 1
    assert only(game.submit_guess("solo"), GameOver).win is True


def test_start_reports_counts_and_first_player():
    game = make_game(tags=["solo", "twilight", "artist:foo", "oc:bar"], first_index=1)
    events = game.start()
    started = only(events, GameStarted)
    assert started.first_player is game.players[1]
    assert started.players == game.players
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


def test_ignored_tag_is_rejected_without_penalty():
    game = make_game(tags=["solo"], first_index=0)
    events = game.submit_guess("source needed")
    assert only(events, GuessRejected).reason is RejectReason.IGNORED_TAG
    assert game.active_player.name == "alice"  # keeps the turn
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
    assert only(events, TurnStarted).player.name == "bob"


def test_moderate_typo_qualifies_as_a_near_miss():
    # ~0.88 similarity: below the old 0.9 bar but at/above the current 0.85 one.
    game = make_game(tags=["twilight"], first_index=0)
    events = game.submit_guess("twiligth")

    near = only(events, NearMiss)
    assert near.closeness >= 85
    assert not any(isinstance(e, TurnStarted) for e in events)
    assert game.active_player.wrong_guesses == 0  # free retry, no strike


def test_near_miss_is_noop_and_keeps_turn():
    game = make_game(tags=["applejack"], first_index=0)
    events = game.submit_guess("applejck")  # a typo, similarity >= 0.85

    near = only(events, NearMiss)
    assert near.player.name == "alice"
    assert near.closeness >= 85
    assert not any(isinstance(e, TurnStarted) for e in events)
    assert game.active_player.name == "alice"  # keeps the turn
    assert game.active_player.wrong_guesses == 0  # no strike
    assert "applejck" not in game.failed_guesses  # can be retried


def test_near_miss_lets_the_player_correct_the_typo():
    game = make_game(tags=["applejack"], first_index=0)
    game.submit_guess("applejck")  # near miss, no penalty, still alice's turn

    events = game.submit_guess("applejack")  # fix the typo
    assert only(events, CorrectGuess).player.name == "alice"
    assert game.players[0].score == 1


def test_unrelated_guess_is_a_plain_wrong_guess():
    game = make_game(tags=["applejack"], first_index=0)
    events = game.submit_guess("xyz")
    only(events, WrongGuess)  # a plain wrong guess, not a near miss
    assert not any(isinstance(e, NearMiss) for e in events)


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
    assert over.unguessed == {"tags": ["solo"]}


def test_solo_loss_crowns_no_winner():
    game = make_game(tags=["solo"], players=["alice"], first_index=0)
    game.submit_guess("x")
    game.submit_guess("y")
    events = game.submit_guess("z")  # eliminated with no one to out-score
    assert only(events, GameOver).winners == []


def test_multiplayer_loss_crowns_top_scorer():
    # Two goal tags so the round can't be won; both players get eliminated.
    game = make_game(
        tags=["aaa", "bbb"], players=["alice", "bob"], first_index=0, elimination_threshold=1
    )
    game.submit_guess("aaa")  # alice scores 1, turn -> bob
    game.submit_guess("miss")  # bob 1st wrong -> eliminated, turn -> alice
    events = game.submit_guess("flop")  # alice 1st wrong -> eliminated, all gone
    over = only(events, GameOver)
    assert over.win is False
    assert [p.name for p in over.winners] == ["alice"]  # led when everyone fell


def test_scoreless_loss_crowns_no_winner():
    game = make_game(
        tags=["aaa", "bbb"], players=["alice", "bob"], first_index=0, elimination_threshold=1
    )
    game.submit_guess("miss")  # alice 1st wrong -> eliminated, turn -> bob
    events = game.submit_guess("flop")  # bob 1st wrong -> eliminated, nobody scored
    assert only(events, GameOver).winners == []


# --- winning & ties ----------------------------------------------------------


def test_win_when_all_regular_tags_guessed():
    game = make_game(tags=["solo"], first_index=0)
    events = game.submit_guess("solo")
    over = only(events, GameOver)
    assert over.win is True
    assert over.unguessed == {}


def test_win_ignores_remaining_artist_and_oc_tags():
    game = make_game(tags=["solo", "artist:foo", "oc:bar"], first_index=0)
    events = game.submit_guess("solo")  # last regular tag
    over = only(events, GameOver)
    assert over.win is True
    assert game.tag_buckets["artists"].tag_count == 1
    assert game.tag_buckets["ocs"].tag_count == 1


def test_unguessed_reports_every_bucket_goal_first():
    game = make_game(tags=["aaa", "bbb", "artist:foo", "oc:bar"], first_index=0)
    game.submit_guess("aaa")  # alice takes one goal tag, turn -> bob
    game.submit_guess("oc:bar")  # bob takes the only oc; "bbb" keeps it running
    assert game.unguessed == {"tags": ["bbb"], "artists": ["artist:foo"]}
    assert list(game.unguessed) == ["tags", "artists"]  # goal bucket leads


def test_unguessed_carries_missed_bonus_tags_at_game_over():
    # The goal bucket completing ends the round with bonus tags still unclaimed.
    game = make_game(tags=["solo", "artist:foo", "oc:bar"], first_index=0)
    over = only(game.submit_guess("solo"), GameOver)
    assert over.unguessed == {"artists": ["artist:foo"], "ocs": ["oc:bar"]}


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


# --- recognizes: the fast path that decides if a guess needs alias resolution -


def test_recognizes_known_and_benign_guesses():
    game = make_game(
        tags=["solo", "artist:foo", "source needed"],
        players=["alice", "bob"],
        query=["cute"],
    )
    assert game.recognizes("solo")  # a goal-bucket tag
    assert game.recognizes("artist:foo")  # a namespaced-bucket tag
    assert game.recognizes("SOLO")  # case-insensitive
    assert game.recognizes("cute")  # default/query tag
    assert game.recognizes("safe")  # rating tag
    assert game.recognizes("source needed")  # ignored tag


def test_recognizes_a_novel_guess_is_false():
    game = make_game(tags=["solo"])
    assert not game.recognizes("big macintosh")  # worth an alias lookup


def test_recognizes_after_a_tag_is_guessed_or_failed():
    game = make_game(tags=["solo", "twilight"], first_index=0)
    game.submit_guess("solo")  # found -> in guessed_tags
    game.submit_guess("wrongo")  # missed -> in failed_guesses
    assert game.recognizes("solo")  # already found, no lookup needed
    assert game.recognizes("wrongo")  # already known wrong, no lookup needed


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
