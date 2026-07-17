"""Tests for the ImageSource abstraction and its static in-memory provider."""

from app.service.image_source import Image, StaticImageSource


def make_image(id: str) -> Image:
    return Image(id=id, tags=["solo"], thumb_url=f"{id}/m", full_url=f"{id}/f")


async def test_empty_source_returns_none():
    source = StaticImageSource([])
    assert await source.random_image([], nsfw=False) is None


async def test_static_source_returns_its_image():
    image = make_image("a")
    source = StaticImageSource([image])
    assert await source.random_image(["cute"], nsfw=True) is image


async def test_static_source_cycles_round_robin():
    a, b = make_image("a"), make_image("b")
    source = StaticImageSource([a, b])
    got = [await source.random_image([], nsfw=False) for _ in range(3)]
    assert got == [a, b, a]
