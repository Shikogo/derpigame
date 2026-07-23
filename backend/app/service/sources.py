"""A source bundle: everything the service needs to run a round from one booru.

A room picks a source by name; the service looks up its ``SourceBundle`` to get
the provider to fetch from, the resolver to canonicalize guesses against, and the
taxonomy that classifies that booru's tags. Bundling them keeps the three in
lockstep — a Furbooru image is always scored with the Furbooru taxonomy — and
lets the service stay agnostic about how many sources exist.
"""

from dataclasses import dataclass

from app.domain.tag_taxonomy import TagTaxonomy
from app.service.image_source import ImageSource
from app.service.tag_resolver import TagResolver


@dataclass(frozen=True)
class SourceBundle:
    image_source: ImageSource
    tag_resolver: TagResolver
    taxonomy: TagTaxonomy | None = None  # None lets Game fall back to its default
