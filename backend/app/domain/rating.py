"""How a booru names and orders its content ratings.

Sources disagree on the vocabulary: Derpibooru has safe/suggestive/questionable/
explicit, e621 drops "suggestive", Danbooru calls its floor "general". A
``RatingLadder`` captures one source's scheme as data — the same trick
``TagTaxonomy`` plays for tag namespaces — so a room can carry a rating cap
without the domain knowing whose vocabulary it is.

``levels`` runs least to most permissive. A room's cap allows every level at or
below it; ``None`` (and the top level, which means the same thing) allows all of
them and needs no search filter at all.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RatingLadder:
    levels: tuple[str, ...]  # least to most permissive

    def knows(self, rating: str) -> bool:
        return rating in self.levels

    def allowed(self, rating: str | None) -> tuple[str, ...]:
        """Every level a cap permits, or ``()`` when it permits all of them."""
        if rating is None or rating == self.levels[-1]:
            return ()
        return self.levels[: self.levels.index(rating) + 1]


DERPIBOORU_RATINGS = RatingLadder(
    levels=("safe", "suggestive", "questionable", "explicit")
)
