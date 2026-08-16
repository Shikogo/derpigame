# CLAUDE.md

Guidance for working in this repo.

## What this is

A real-time multiplayer party game: players join a room, get a random image from
Derpibooru, and take turns guessing its tags. Vue frontend, FastAPI +
python-socketio backend.

The core is built and playable. `ROADMAP.md` tracks what's left — config,
persistence, a hardened image client, e621, accounts, deployment.

## Repo layout

- `backend/` — FastAPI + python-socketio. Layered (see below).
- `frontend/` — Vue app (Vite + Pinia + Vue Router + Tailwind).

## Backend architecture

Strict layering — keep dependencies pointing one direction:

- `app/domain/` — pure game rules (`Game`, `Room`, `User`, `TagTaxonomy`,
  `TagBucket`). **No framework imports** (no FastAPI, no socketio, no HTTP) and
  no importing an outer layer. Tag classification is a data-driven `TagTaxonomy`
  value object injected into `Game`. Methods return event objects describing what
  happened; they don't emit or render. This is what makes the domain
  unit-testable without an app context.
- `app/service/` — orchestrates domain objects, image sources, persistence.
- `app/transport/` — thin FastAPI + socketio adapters: parse message, call
  service, serialize result to JSON, emit.
- `app/persistence/` — repositories (DB access), swappable/mockable.
- `app/config/` — centralized Pydantic `Settings`, injected.

This is enforced, not just documented: ruff fails the lint if `domain/` imports a
framework, an HTTP client, or any outer layer. If you hit that error, the fix is
almost never an ignore — the logic belongs in `service/`.

The frontend mirrors the same discipline: a pure `(state, event) => state`
reducer (`src/game/reducer.ts`) holds the game-view logic with no Vue or socket
dependency, and Pinia stores are a thin reactive shell over it.

## Checks — run these before committing

Backend, from `backend/`:

```bash
.venv/bin/ruff check app tests && .venv/bin/ruff format app tests
.venv/bin/python -m pytest
```

Frontend, from `frontend/`:

```bash
npm run lint && npm run format && npm run typecheck && npm run test
npm run e2e   # starts both servers itself; needs the backend venv
```

CI runs the same set on every push and every PR
(`.github/workflows/ci.yml`), and the Fly and Cloudflare Pages deploys gate on
it, so a red `main` doesn't ship. A push to a branch publishes a Pages preview
at `<branch>.derpigame.pages.dev`; only `main` reaches production. There's no pre-commit hook — run the checks before
committing rather than letting the runner find it. `DEVELOPMENT.md` has
the details, including why the configs are the way they are; don't add layout
rules to ESLint (Prettier owns formatting) and use `npm run typecheck`, never
`tsc --noEmit`.

## Working style

- New logic ships with unit tests, frontend included — not just backend.
  Presentation-only tweaks don't need them.
- Suggest improvements rather than doing the literal thing asked when the literal
  thing is worse. Flag odd behavior instead of quietly working around it.
- A small Playwright suite (`frontend/e2e/`, `npm run e2e`) covers the flows that
  need a real socket: a round from lobby to results, the guess verdicts, and two
  players sharing a turn. It runs against the offline backend, whose fixed images
  have known tags — that fixture is what makes the assertions possible. Keep it
  small; anything provable without a browser belongs in a unit test.
- Beyond that, verify by hand in the browser (two tabs, or `./run-local.sh
  --dev`).
- The wire contract lives in two mirrored places: the Python serializers
  (`app/service/serialization.py`, `app/transport/`) and `src/types/wire.ts`.
  Change both together — there's no case-translation layer.

## Conventions

- **Commits: Conventional Commits** (`feat:`, `fix:`, `refactor:`, `test:`,
  `docs:`, `chore:`, etc.). Scope optional, e.g. `feat(domain): add turn rotation`.
- Commit finished work before starting something unrelated — especially before a
  formatter or codemod, which can't be unpicked per-hunk afterwards.
- Work on a branch, then merge into `main` — don't commit directly to `main`
  unless explicitly told to. Branch first (`git checkout -b`) before starting.
- Only commit or push when asked.
