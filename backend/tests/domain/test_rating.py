"""RatingLadder: turning a room's rating cap into the levels it permits."""

from app.domain.rating import DERPIBOORU_RATINGS, RatingLadder

LADDER = RatingLadder(levels=("safe", "spicy", "hot"))


def test_a_cap_allows_itself_and_everything_below():
    assert LADDER.allowed("safe") == ("safe",)
    assert LADDER.allowed("spicy") == ("safe", "spicy")


def test_no_cap_allows_everything_without_naming_levels():
    """() means "emit no filter" — the top level and None are the same thing."""
    assert LADDER.allowed(None) == ()
    assert LADDER.allowed("hot") == ()


def test_knows_only_its_own_vocabulary():
    assert LADDER.knows("spicy")
    assert not LADDER.knows("suggestive")  # another source's word


def test_derpibooru_ladder_runs_least_to_most_permissive():
    assert DERPIBOORU_RATINGS.allowed("questionable") == (
        "safe",
        "suggestive",
        "questionable",
    )
