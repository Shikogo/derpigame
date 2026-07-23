"""RatingAxis: turning a room's cap into the tags it rules out."""

from app.domain.rating import PHILOMENA_AXES, RatingAxis, RatingLevel

AXIS = RatingAxis(
    key="heat",
    label="Heat",
    levels=(
        RatingLevel("mild", ("mild",)),
        RatingLevel("spicy", ("spicy",)),
        RatingLevel("hot", ("hot",)),
    ),
)


def test_a_cap_excludes_only_what_sits_above_it():
    assert AXIS.excluded("mild") == ("spicy", "hot")
    assert AXIS.excluded("spicy") == ("hot",)


def test_the_top_level_and_no_cap_exclude_nothing():
    assert AXIS.excluded("hot") == ()
    assert AXIS.excluded(None) == ()


def test_an_unknown_cap_excludes_nothing_rather_than_guessing():
    """Another source's level name must never silently narrow a search."""
    assert AXIS.excluded("scorching") == ()
    assert not AXIS.knows("scorching")


def _axis(key: str) -> RatingAxis:
    return next(a for a in PHILOMENA_AXES if a.key == key)


def test_capping_the_rating_axis_leaves_the_darkness_axis_alone():
    """The axes are independent: a rating cap says nothing about grimdark."""
    assert _axis("rating").excluded("questionable") == ("explicit",)


def test_the_darkness_floor_excludes_every_dark_tag():
    assert _axis("darkness").excluded("none") == (
        "semi-grimdark",
        "grimdark",
        "grotesque",
    )
