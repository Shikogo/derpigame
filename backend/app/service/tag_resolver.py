"""Resolving a guessed tag to its canonical name.

Derpibooru stores images under canonical tags only, so a guessed alias (``bm``)
never matches the tag on the image (``big macintosh``) by string alone. A
``TagResolver`` maps a guess to its canonical tag; the game then matches on that.

Resolution is best-effort: an unknown or already-canonical tag comes back
unchanged, and providers must not raise on failure — a lookup that can't be made
just degrades to literal matching. ``NullTagResolver`` is the no-op default;
``StaticTagResolver`` is a fixed map for tests and offline development.
"""

from abc import ABC, abstractmethod


class TagResolver(ABC):
    @abstractmethod
    async def canonicalize(self, tag: str) -> str:
        """Return the canonical name for ``tag``, or ``tag`` unchanged.

        Unchanged means the tag is already canonical, has no known alias, or the
        lookup couldn't be completed. Never raises.
        """


class NullTagResolver(TagResolver):
    """Resolves nothing — every tag is returned as-is (literal matching)."""

    async def canonicalize(self, tag: str) -> str:
        return tag


class StaticTagResolver(TagResolver):
    """Resolves from a fixed ``alias -> canonical`` map; passes unknowns through."""

    def __init__(self, aliases: dict[str, str] | None = None):
        self._aliases = {k.lower(): v for k, v in (aliases or {}).items()}

    async def canonicalize(self, tag: str) -> str:
        return self._aliases.get(tag.lower(), tag)
