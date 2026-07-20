"""How a booru's tags are classified for the game.

Different sources namespace their tags differently: Derpibooru uses ``artist:``
and ``oc:`` and hides plot points behind ``spoiler:``; e621 adds ``character:``,
``species:``, ``copyright:`` and its own rating names. A ``TagTaxonomy`` captures
one source's scheme as data so the ``Game`` stays source-agnostic — the service
picks the taxonomy that matches whichever image source it pulled from.

- ``namespaces`` route prefixed tags into their own buckets (guessable for
  points, but not required to win). Insertion order is display order.
- ``goal_bucket`` holds the plain, un-namespaced tags — the ones that must all
  be guessed to win.
- ``rating_tags``, ``ignored_tags`` and ``ignored_prefixes`` are dropped: never
  guessable, never shown. ``ignored_tags`` covers plain tags that can't be
  derived from the image (source-link housekeeping, say) so they mustn't gate a
  win.

The constants below carry only what's *structural* about a source — its
namespaces and rating vocabulary, facts you can't change by preferring
otherwise. Which housekeeping tags to ignore is curation, so it lives in
``config.toml`` and is applied over the constant at startup; a taxonomy built
here on its own therefore ignores nothing.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TagTaxonomy:
    namespaces: dict[str, str]  # bucket key -> prefix, e.g. {"artists": "artist:"}
    rating_tags: frozenset[str] = frozenset()
    ignored_tags: frozenset[str] = frozenset()
    ignored_prefixes: tuple[str, ...] = ()
    goal_bucket: str = "tags"

    def bucket_for(self, tag: str) -> str:
        """The bucket key a tag belongs to (a namespace, or the goal bucket)."""
        for key, prefix in self.namespaces.items():
            if tag.startswith(prefix):
                return key
        return self.goal_bucket

    def prefix_of(self, bucket_key: str) -> str:
        """The namespace prefix for a bucket, or ``""`` for the goal bucket."""
        return self.namespaces.get(bucket_key, "")

    def bare(self, tag: str) -> str:
        """``tag`` without its namespace prefix; unchanged if it has none."""
        return tag[len(self.prefix_of(self.bucket_for(tag))) :]

    def is_droppable(self, tag: str) -> bool:
        """Whether a tag is a rating, ignored outright, or under an ignored prefix."""
        return (
            tag in self.rating_tags
            or tag in self.ignored_tags
            or tag.startswith(self.ignored_prefixes)
        )


DERPIBOORU_TAXONOMY = TagTaxonomy(
    namespaces={
        "artists": "artist:",
        "ocs": "oc:",
        "comics": "comic:",
        "fanfics": "fanfic:",
        "series": "series:",
    },
    rating_tags=frozenset(
        {
            "explicit",
            "grimdark",
            "grotesque",
            "questionable",
            "safe",
            "semi-grimdark",
            "suggestive",
        }
    ),
)
