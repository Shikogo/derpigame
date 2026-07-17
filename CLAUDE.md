# CLAUDE.md

Guidance for working in this repo.

## What this is

A rewrite of `derpigame-legacy` (Flask + Flask-SocketIO + server-rendered Jinja)
into a Vue frontend backed by a FastAPI + python-socketio API/WebSocket layer.
It's a real-time multiplayer party game: players join a room, get a random image
from Derpibooru, and take turns guessing its tags.

The full rewrite plan lives in `derpigame-rewrite-plan.md` — read it for the
architecture rationale, known legacy bugs, and build phases.

## Repo layout

- `backend/` — FastAPI + python-socketio. Layered (see below).
- `frontend/` — Vue app (Vite + Pinia + Vue Router). Not scaffolded yet.
- The legacy app is at `../derpigame-legacy` for reference (not part of this repo).

## Backend architecture

Strict layering — keep dependencies pointing one direction:

- `app/domain/` — pure game rules (`Game`, `Room`, `User`, `TagTaxonomy`,
  `TagBucket`). **No framework imports** (no FastAPI, no socketio, no HTTP).
  Tag classification is a data-driven `TagTaxonomy` value object injected into
  `Game`, not a per-source `TagType`. Methods return result
  objects describing what happened; they don't emit or render. This is what
  makes the domain unit-testable without an app context.
- `app/service/` — orchestrates domain objects, image sources, persistence.
- `app/transport/` — thin FastAPI + socketio adapters: parse message, call
  service, serialize result to JSON, emit.
- `app/persistence/` — repositories (DB access), swappable/mockable.
- `app/config/` — centralized Pydantic `Settings`, injected.

If you find yourself importing socketio or FastAPI into `domain/`, stop — the
logic belongs in a different layer.

## Porting mindset

This is a rewrite, not a transcription. The legacy code is low quality — you're
**encouraged to suggest improvements** to game logic, structure, naming, and
behavior as you port, rather than faithfully reproducing legacy quirks. When you
spot a legacy bug or an odd behavior, flag it and propose the fix instead of
silently carrying it over. Preserving intended game rules matters; preserving
accidental behavior does not.

## Conventions

- **Commits: Conventional Commits** (`feat:`, `fix:`, `refactor:`, `test:`,
  `docs:`, `chore:`, etc.). Scope optional, e.g. `feat(domain): add turn rotation`.
- Wire protocol is **JSON**, not HTML fragments (unlike the legacy app).
- Only commit or push when asked.
