"""A bucket of tags of one kind.

Tracks the tags still to be guessed and removes them as they're found.
Which kind a bucket represents (regular / artist / OC) is the identity given
by the key it's stored under in ``Game.tag_buckets``; display names and grammar
belong to the presentation layer.
"""

from __future__ import annotations


class TagBucket:
    def __init__(self, tags: list[str]):
        self.tags = list(tags)

    @property
    def tag_count(self) -> int:
        return len(self.tags)

    def take(self, guess: str) -> bool:
        """Remove ``guess`` from this bucket if present, returning whether it matched."""
        if guess in self.tags:
            self.tags.remove(guess)
            return True
        return False
