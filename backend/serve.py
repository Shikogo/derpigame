"""Single-origin serve: the real Derpibooru backend plus the built frontend from
one process, so a single URL (behind one tunnel) fronts both the SPA and the
websocket. For playing with friends over a cloudflared/ngrok tunnel.

Build the frontend first (from frontend/):
    VITE_BACKEND_URL= npm run build -- --base=/ --outDir dist-local

Then run (from backend/):
    .venv/bin/uvicorn serve:app --host 0.0.0.0 --port 8000

The online counterpart to dev_server.py (offline/static) and app.main:app
(API only) — a convenience for local hosting, not part of the shipped app.
"""

from pathlib import Path

from app.transport.app import create_app

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist-local"

if not DIST.is_dir():
    raise SystemExit(
        f"Frontend build not found at {DIST}. Build it first:\n"
        "  cd frontend && VITE_BACKEND_URL= npm run build -- --base=/ --outDir dist-local"
    )

app = create_app(static_dir=DIST)
