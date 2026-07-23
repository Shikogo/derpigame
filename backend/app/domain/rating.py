"""How a booru names, groups, and orders its content ratings.

Sources disagree on the vocabulary — e621 drops "suggestive", Danbooru calls its
floor "general" — and they rate along more than one independent axis. Derpibooru
rates sexual content and darkness separately: an image can be explicit, or
grimdark, or both, or carry only one of the two. A ``RatingAxis`` captures one
such scale as data, the same trick ``TagTaxonomy`` plays for tag namespaces, so
a room can carry a cap per axis without the domain knowing whose vocabulary it
is.

Caps are expressed as **exclusions**, not as the set of levels they permit. A
positive filter would have to name a tag on every axis, which wrongly drops the
tens of thousands of images that carry a tag on one axis and none on the other —
and OR-ing the axes together to fix that lets an over-cap image back in through
whichever axis it does satisfy. Excluding only what sits above the cap says
nothing about images with no tag on that axis, which is exactly right.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RatingLevel:
    name: str
    tags: tuple[str, ...] = ()  # the tags this level introduces


@dataclass(frozen=True)
class RatingAxis:
    key: str  # stable identifier, used on the wire and as a room's cap key
    label: str  # what to call this axis in the UI
    levels: tuple[RatingLevel, ...]  # least to most permissive

    def knows(self, level: str) -> bool:
        return any(step.name == level for step in self.levels)

    def excluded(self, cap: str | None) -> tuple[str, ...]:
        """The tags a cap rules out, or ``()`` when it rules out nothing.

        An unrecognized cap excludes nothing rather than guessing, so a level
        name from another source can never silently narrow a search.
        """
        if cap is None:
            return ()
        names = [step.name for step in self.levels]
        if cap not in names:
            return ()
        above = self.levels[names.index(cap) + 1 :]
        return tuple(tag for step in above for tag in step.tags)


# Philomena's two scales, shared by every instance (Derpibooru, Furbooru, …).
# "none" introduces no tags: capping there excludes every darkness tag, while the
# top level of either axis excludes nothing.
PHILOMENA_AXES = (
    RatingAxis(
        key="rating",
        label="Rating",
        levels=(
            RatingLevel("safe", ("safe",)),
            RatingLevel("suggestive", ("suggestive",)),
            RatingLevel("questionable", ("questionable",)),
            RatingLevel("explicit", ("explicit",)),
        ),
    ),
    RatingAxis(
        key="darkness",
        label="Darkness",
        levels=(
            RatingLevel("none"),
            RatingLevel("semi-grimdark", ("semi-grimdark",)),
            RatingLevel("grimdark", ("grimdark",)),
            RatingLevel("grotesque", ("grotesque",)),
        ),
    ),
)
