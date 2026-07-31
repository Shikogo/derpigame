"""Offline dev server: the app wired to a fixed set of images with known tags.

Runs the whole stack with no Derpibooru token, no network and no rate limits.
Because the tag list is known, every verdict the UI can render is reachable on
purpose rather than by luck — correct, alias, near miss, strike, rejection.

Run: ``.venv/bin/uvicorn dev_server:app --reload``, or ``./run-local.sh --offline``.

Rounds alternate between the two images, which name themselves on the picture —
check the label before reaching for the answer key, since which one comes up
depends on how many rounds the server has already served.

======================  ==================  =========================
verdict                 LIBRARY             MEADOW
======================  ==================  =========================
correct, plain tag      ``book``            ``cloud``
correct, bonus tag      ``littlepip``       ``testmare``
correct via alias       ``ts``, ``twily``   ``rd``, ``dashie``
near miss (free retry)  ``unicorm``         ``pegasis``
wrong (a strike)        ``magik``           ``magik``
rejected, rating tag    ``safe``            ``safe``
rejected, ignored tag   ``commission``      ``commission``
======================  ==================  =========================

Clearing the plain tags — eight on LIBRARY, six on MEADOW — wins the round, which
is the way to the results screen; three strikes is the way to the other ending.
Rejections cost nothing, so those cards are free to look at mid-turn. For
``default_tag``, put one of the image's tags in the room's query; for a timeout,
shorten the turn in the room settings.
"""

from urllib.parse import quote

from app.config import load_settings
from app.service.image_source import Image, StaticImageSource
from app.service.tag_resolver import StaticTagResolver
from app.transport.app import create_app


def _placeholder(title: str, start: str, stop: str) -> str:
    """A labelled gradient as a data URI — no file to serve, no host to reach."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        f"<stop offset='0' stop-color='{start}'/><stop offset='1' stop-color='{stop}'/>"
        "</linearGradient></defs>"
        "<rect width='1200' height='800' fill='url(#g)'/>"
        "<circle cx='300' cy='240' r='140' fill='#ffffff' opacity='0.8'/>"
        "<rect x='760' y='460' width='300' height='220' rx='24' fill='#111827' opacity='0.75'/>"
        "<text x='600' y='430' font-family='monospace' font-size='64' fill='white' "
        f"text-anchor='middle'>{title}</text></svg>"
    )
    return "data:image/svg+xml," + quote(svg)


_LIBRARY = _placeholder("LIBRARY", "#7c3aed", "#16a34a")
_MEADOW = _placeholder("MEADOW", "#0ea5e9", "#f59e0b")

# `safe` and `commission` sit on both images on purpose: one is a rating tag, the
# other ignored by config curation, so both rejections are always in reach.
IMAGES = [
    Image(
        id="1",
        tags=[
            "twilight sparkle",
            "unicorn",
            "book",
            "library",
            "magic",
            "mare",
            "solo",
            "smiling",
            "artist:shikogo",
            "oc:littlepip",
            "oc:blackjack",
            "safe",
            "commission",
        ],
        thumb_url=_LIBRARY,
        full_url=_LIBRARY,
        page_url="https://derpibooru.org/images/1",
        source_url="https://example.com/library",
    ),
    Image(
        id="2",
        tags=[
            "rainbow dash",
            "pegasus",
            "cloud",
            "flying",
            "grin",
            "outdoors",
            "artist:tester",
            "oc:testmare",
            "safe",
            "commission",
        ],
        thumb_url=_MEADOW,
        full_url=_MEADOW,
        page_url="https://derpibooru.org/images/2",
        source_url=None,
    ),
]

# Stands in for the booru's alias table. An abbreviation, a nickname and a plural
# — each puts a different distance between what was typed and what was scored.
ALIASES = {
    "ts": "twilight sparkle",
    "twily": "twilight sparkle",
    "rd": "rainbow dash",
    "dashie": "rainbow dash",
    "books": "book",
    "smile": "smiling",
}

# Long turns by default: a harness gets left sitting mid-round while something is
# inspected, and a timeout there is noise rather than a finding.
_base = load_settings()
settings = _base.model_copy(
    update={"room_defaults": _base.room_defaults.model_copy(update={"turn_seconds": 300.0})}
)

app = create_app(
    settings=settings,
    image_source=StaticImageSource(IMAGES),
    tag_resolver=StaticTagResolver(ALIASES),
)
