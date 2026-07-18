"""Local offline dev server: wires the app to a static in-memory image source,
so the full stack runs with no Derpibooru token, network, or API rate limits,
and the served image's tags are known for exercising the guess loop.

Run: .venv/bin/uvicorn dev_server:app --reload

The offline alternative to `app.main:app` (which uses the real image source) —
a dev convenience, not part of the shipped app.
"""

from urllib.parse import quote

from app.service.image_source import Image, StaticImageSource
from app.transport.app import create_app

_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
    "<stop offset='0' stop-color='%237c3aed'/><stop offset='1' stop-color='%2316a34a'/>"
    "</linearGradient></defs>"
    "<rect width='1200' height='800' fill='url(%23g)'/>"
    "<circle cx='400' cy='300' r='160' fill='%23ffffff' opacity='0.85'/>"
    "<rect x='700' y='420' width='320' height='240' rx='20' fill='%23111827' opacity='0.8'/>"
    "<text x='600' y='740' font-family='monospace' font-size='44' fill='white' "
    "text-anchor='middle'>DERPIGAME E2E</text></svg>"
)
_DATA_URI = "data:image/svg+xml," + quote(_SVG, safe="%")

IMAGE = Image(
    id="1",
    tags=["solo", "pony", "cute", "artist:tester"],
    thumb_url=_DATA_URI,
    full_url=_DATA_URI,
    page_url="https://derpibooru.org/images/1",
    source_url="https://example.com/original",
)

app = create_app(image_source=StaticImageSource([IMAGE]))
