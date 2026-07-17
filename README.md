# derpigame

A real-time multiplayer party game: players join a room, get a random image from
Derpibooru, and take turns guessing its tags. Three wrong guesses eliminate you;
most points when the tags are all guessed (or everyone's out) wins.

This repo is a rewrite of the legacy Flask app into a **FastAPI + python-socketio**
backend and a **Vue** frontend. See [`derpigame-rewrite-plan.md`](derpigame-rewrite-plan.md)
for the architecture and build phases.

## Repo layout

```
backend/    FastAPI + socketio API/WebSocket layer (layered: domain/service/transport/persistence/config)
frontend/   Vue app (Vite + Pinia + Vue Router) — not scaffolded yet
```

## Backend

Requires **Python 3.12+**.

### Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running tests

The domain layer is pure (no framework or app context), so the suite runs in
well under a second. From `backend/`:

```bash
.venv/bin/python -m pytest          # run everything
.venv/bin/python -m pytest -v       # verbose, one line per test
.venv/bin/python -m pytest tests/domain/test_game.py   # a single file
.venv/bin/python -m pytest -k elimination              # tests matching a keyword
```

Config lives in `backend/pytest.ini` (test discovery, import path, and
`asyncio_mode = auto` so `async def` tests run without a per-test marker).

## Architecture

Dependencies point one way:

- **`domain`** — pure game rules (`Game`, `Room`, `User`, `TagBucket`). Methods
  return event objects describing what happened; no framework imports, no I/O.
  This is what lets the tests run with no app context.
- **`service`** — orchestrates the domain, image sources, and serialization of
  domain events into JSON payloads.
- **`transport`** — thin FastAPI + socketio adapters: parse a message, call the
  service, emit the resulting JSON.

The wire protocol is JSON — the backend emits structured, typed events and the
Vue client owns all rendering.
