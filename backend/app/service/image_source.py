"""Abstraction over booru image providers (Derpibooru, e621, ...).

The domain never touches this; the service asks an ``ImageSource`` for a random
image and hands the image's tags to a new game. Concrete providers (async HTTP
clients with retry/backoff) implement the interface; ``StaticImageSource`` is a
deterministic in-memory provider for tests and offline development.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Image:
    id: str
    tags: list[str]
    thumb_url: str  # medium-sized preview for the viewer
    full_url: str  # full-resolution image
    page_url: str = ""  # booru page for the image
    source_url: str | None = None  # external source, if the booru has one


@dataclass(frozen=True)
class SearchOptions:
    """What a room wants from a provider, beyond the search tags themselves.

    Grouped into one object so a new room setting doesn't widen every
    ``random_image`` signature and test double.
    """

    nsfw: bool = False


class ImageSourceError(Exception):
    """Raised when a source fails to answer (network error, timeout, bad status)."""


class ImageSource(ABC):
    @abstractmethod
    async def random_image(self, query: list[str], *, options: SearchOptions) -> Image | None:
        """Return a random image matching ``query``, or ``None`` if none match.

        Raises ``ImageSourceError`` on provider/transport failures (distinct
        from an empty result, which is a normal ``None``).
        """


class StaticImageSource(ImageSource):
    """Serves a fixed list of images in round-robin order.

    An empty list models "no matching image" by always returning ``None``.
    """

    def __init__(self, images: list[Image] | None = None):
        self._images = list(images or [])
        self._index = 0

    async def random_image(self, query: list[str], *, options: SearchOptions) -> Image | None:
        if not self._images:
            return None
        image = self._images[self._index % len(self._images)]
        self._index += 1
        return image
