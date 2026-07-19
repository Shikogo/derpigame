# derpigame

A real-time multiplayer party game: players join a room, get a random image from
Derpibooru, and take turns guessing its tags. Three wrong guesses eliminate you;
most points when the tags are all guessed (or everyone's out) wins.

This repo is a rewrite of the legacy Flask app into a **FastAPI + python-socketio**
backend and a **Vue** frontend. The core rewrite is complete and playable
end-to-end — both layers are built and tested; a database and user accounts are
the main pieces still to come (room history and stats are in-memory for now). See
[`derpigame-rewrite-plan.md`](derpigame-rewrite-plan.md) for the architecture and
remaining phases.

## Repo layout

```
backend/    FastAPI + socketio API/WebSocket layer (layered: domain/service/transport/persistence/config)
frontend/   Vue app (Vite + Pinia + Vue Router)
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

### Running the server

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000
```

`app.main:app` is the FastAPI app (with the Socket.IO server mounted) built by
`create_app()`. `--reload` restarts on code changes — drop it for a plain run.
The frontend talks to it at `http://localhost:8000` (see the Frontend section).

For frontend work without a Derpibooru token or network, run the offline dev
server instead — it serves a fixed image from a static source:

```bash
.venv/bin/uvicorn dev_server:app --reload   # http://localhost:8000
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

## Frontend

Requires **Node 20+** (developed on Node 22). Uses npm.

### Setup

```bash
cd frontend
npm install
cp .env.example .env   # sets VITE_BACKEND_URL=http://localhost:8000
```

### Running the dev server

```bash
npm run dev            # http://localhost:5173
```

Vite serves the app with hot-module reload and proxies nothing — it talks to the
backend directly over `VITE_BACKEND_URL`, so start the backend (above) in another
terminal. Open the app in two tabs to play a room against yourself.

### Running tests

```bash
npm run test           # Vitest, single run
npm run test:watch     # Vitest, watch mode
npm run typecheck      # vue-tsc type check
npm run build          # type check + production build
```

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

On the frontend, that same discipline repeats: a pure `(state, event) => state`
reducer folds the `game_events` stream into view state with no Vue or socket
dependency, so the game logic is unit-testable in isolation. Pinia stores are a
thin reactive shell over it, a typed `socket.io-client` wrapper carries the wire
contract (mirrored exactly in `src/types/wire.ts`), and components stay
presentational.
