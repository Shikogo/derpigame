"""The no-op and static TagResolver stand-ins."""

from app.service.tag_resolver import NullTagResolver, StaticTagResolver


async def test_null_resolver_returns_every_tag_unchanged():
    resolver = NullTagResolver()

    assert await resolver.canonicalize("bm") == "bm"


async def test_static_resolver_maps_known_aliases():
    resolver = StaticTagResolver({"bm": "big macintosh"})

    assert await resolver.canonicalize("bm") == "big macintosh"


async def test_static_resolver_is_case_insensitive():
    resolver = StaticTagResolver({"BM": "big macintosh"})

    assert await resolver.canonicalize("Bm") == "big macintosh"


async def test_static_resolver_passes_through_unknowns():
    resolver = StaticTagResolver({"bm": "big macintosh"})

    assert await resolver.canonicalize("pony") == "pony"
