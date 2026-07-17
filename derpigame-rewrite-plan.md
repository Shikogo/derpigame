# Derpigame Rewrite Plan (Vue + API)

Remaking `derpigame-legacy` (Flask + Flask-SocketIO + server-rendered Jinja) into a modern Vue frontend backed by a proper API + WebSocket layer.

---

## 1. What the legacy app actually does

A real-time multiplayer party game:
- Players join a "room" (nickname + room name, no real auth)
- A random image is pulled from Derpibooru via the `derpibooru` search API
- Players take turns guessing the image's tags; 3 wrong guesses = eliminated
- Most points when all tags are guessed (or all players eliminated) wins
- All room/game/session state lives in **plain Python dicts in server memory** — no database
- Frontend is server-rendered Jinja partials pushed over Socket.IO (`reload_users`, `reload_source`, etc. emit pre-rendered HTML, not JSON)

Codebase is small: core logic (`data.py`, `events.py`, `routes.py`, `utility.py`) is under 600 lines total.

---

## 2. Known bugs in the legacy logic (fix during port)

1. **Crash in `Room.start_game`**: `say("No players are ready!", room, 'status')` — `room` isn't defined in scope, should be `self.name`. Throws `NameError` if "start" is hit with zero ready players.
2. **Broken uniqueness check** in `forms.py`: `unique_name_check` compares a string against `User` objects (`field.data in sessions.values()`), which is always `False` since `User` has no `__eq__`. Username uniqueness is currently a no-op.
3. **Race condition** between guess submission and turn timeout: `game.timer.cancel()` doesn't guarantee the timeout callback isn't already mid-execution on its own thread. No lock protects `self.players` — worst case, double turn-advance or corrupted game state. Root cause is architectural (see §3b) — the real fix is removing the second thread, not just adding a lock.
4. Hardcoded `SECRET_KEY = "you-will-never-guess-this"` — move to an environment variable.

---

## 3. Architecture decisions

- **Backend language: stick with Python.** The game logic (`data.py`) ports over nearly unchanged — turn rotation, elimination/reindexing, fuzzy-match scoring via `difflib`, tag-type bucketing. The `derpibooru` package is already Python. Minimizes rewrite risk while also rebuilding the entire frontend.
- **Framework: FastAPI + `python-socketio`** as the natural modern replacement for Flask-SocketIO — async, real request validation via Pydantic, free API schema for the Vue side to consume.
- **Wire protocol change (the actual hard part):** replace server-rendered HTML fragments with structured **JSON payloads**. Vue components own rendering; the backend just emits state (tag lists, user lists, scores, timer state).
- **State storage:** keep in-memory (matches original, fine for single-instance hobby deploy). Only move to Redis + Socket.IO Redis adapter if running multiple backend instances — not needed at this scale.
- **Turn timer:** replace `threading.Timer` with an `asyncio` task on FastAPI's own event loop (see §3b) — removes the race condition as a category, not just this one instance of it.

### 3b. Separation of concerns — current problems and target layering

The legacy code mixes four different jobs inside one set of classes: game rules, network transport (`emit()` calls), presentation (`render_template()` calls), and process-level state (`threading.Timer` mutating shared state from a second thread). That's why bug #3 exists, and it's also why the legacy code has no unit tests — you can't exercise `Game.process_guess()` without a live Flask request context, because it calls `emit()` directly. Worth fixing properly during the rewrite rather than porting the same shape:

| Layer | Responsibility | Depends on |
|---|---|---|
| **Domain** (`Game`, `Room`, `User`, `TagType`) | Pure game rules. Methods take input, return a result object describing what happened (`CorrectGuess`, `WrongGuess`, `PlayerEliminated`, `GameOver`) — no `emit()`, no `render_template()`, no socketio/Flask imports at all. | Nothing but the standard library |
| **Application/service** | Orchestrates domain objects; calls the `ImageSource` abstraction (Derpibooru/e621) and persistence (stats, alias cache); turns domain result objects into outbound event data | Domain layer, `ImageSource`, repositories |
| **Transport** (FastAPI + socketio handlers) | Thin adapters only: parse the incoming socket/HTTP message, call the service layer, take the returned event(s), serialize to JSON, emit | Application layer |
| **Persistence** (repositories) | DB access for users, stats, alias cache — swappable/mockable, not called directly from domain code | DB / SQLite |
| **State/session store** | Replaces the global `rooms = {}` / `sessions = {}` module-level dicts with an injected store class (in-memory now, Redis-backed later without touching callers) | — |
| **Config** | Centralized `Settings` object (Pydantic Settings), injected — replaces scattered hardcoded constants | — |

**Why this matters beyond tidiness:**
- **Testability**: domain layer has zero framework dependencies, so unit tests (already planned in Phase 1) can run in milliseconds with no app context, no mocking `emit()`.
- **Fixes bug #3 structurally**: the turn timer becomes an `asyncio.Task` that, on expiry, feeds a "timeout" event through the *same* single-threaded processing path as a manual guess — there's no longer a second thread that can race with the main flow, so the whole bug class disappears rather than being patched with a lock.
- **Sets up every Phase 2/3 feature cleanly**: persistent stats hook in as another consumer of domain result objects (no change to game logic); the `ImageSource` abstraction for e621 sits cleanly in the service layer; alias caching is just another repository.

---

## 4. Build phases

1. **Backend API + WebSocket layer** — port `data.py` game logic into the layered structure above (domain / service / transport), replace HTML-fragment emits with JSON, fix bug #2 (real name-uniqueness check) and bug #3 (timer race, via the asyncio-task redesign) along the way.
2. **Unit tests** — cover the domain layer in isolation (turn order, elimination, fuzzy-match scoring, tie detection) — no app context needed given the layering above.
3. **Vue frontend** — components for login, room/lobby, image viewer, chat, guessed/incorrect tag lists, user list, score display. Pinia store for room/game state.
4. **Integration tests** — full flow through the transport layer: join room → ready up → start game → guess → win/lose.
5. **Bugfixes** — fix #1 (`room` → `self.name`) and #4 (`SECRET_KEY` env var) as encountered.
6. **New features** — see Phase 2/3 below.

---

## 5. Phase 2 — extended features (after core port is stable)

Suggested order matters here — accounts before stats, since stats should key off a real user ID rather than a throwaway session UUID.

1. **Better config** — easiest. Move hardcoded values (`SECRET_KEY`, default query, timer duration, elimination threshold) into a centralized `Settings` object (see §3b), expose relevant bits through the API for room-level config instead of just the query textbox.
2. **E621 integration** — easy-to-moderate. Structurally similar to Derpibooru (booru-style JSON API). Specifics: requires a custom User-Agent header (e621 blocks generic ones), username+API-key auth for anything beyond anonymous search, and a different tag/rating vocabulary than Derpibooru's — `TagType` bucketing needs adjusting per source. Implement behind the same `ImageSource` interface as Derpibooru so rooms can pick a source.
3. **User accounts** — hardest, reshapes other decisions. Needs a `users` table with persistent IDs (replacing the throwaway per-session UUID), password hashing (bcrypt/argon2) or OAuth (GitHub login fits this project well), and token/session handling that extends into WebSocket auth on connect.
4. **Persistent stats** — moderate, built on top of accounts. Needs a database (SQLite is fine), a schema for users/games/results, a write path when `Game` emits its `GameOver` result object (see §3b — this is a clean hook point), and new read endpoints (`/stats/{user}`, `/leaderboard`).

---

## 6. Phase 3 — Derpibooru improvements

**API handling** (~a day, mostly plumbing):
- Wrap Derpibooru calls in a `DerpibooruClient` class instead of inline calls scattered across files — mockable, and a natural home for the `ImageSource` interface shared with e621.
- Go async: replace the sync `derpibooru` package's `requests` calls with `httpx.AsyncClient` calls directly against Derpibooru's REST API, since a blocking call inside a socket handler stalls that worker for every room.
- Handle real failure modes — network errors, timeouts, 429 rate limits — with retry/backoff and a clean in-room error message, instead of the current bare `StopIteration`-only handling.
- Respect rate limits proactively (request spacing/backoff).

**Alias handling** (~2-3 days, replacing the static 355KB `alias.json`):
- On an unmatched guess, query Derpibooru's tag search API directly — it returns each tag's canonical form if the guess is an alias, so resolution can happen live instead of from a stale snapshot.
- Cache results in a local table (`guess → canonical_tag`, with timestamp) so repeat guesses don't round-trip to the API — matters for game responsiveness.
- Optional: background job to periodically refresh stale cache entries.
- Lives behind the same `ImageSource` interface as search, since alias resolution is booru-specific too.

---

## 7. Deployment plan

**Target: $0/month**

| Piece | Where | Notes |
|---|---|---|
| Frontend (Vue static build) | **GitHub Pages** | Set `base: '/repo-name/'` in `vite.config.js` + Vue Router base to match. Use Vue Router **hash mode** to avoid needing a `404.html` SPA-redirect trick. Deploy via GitHub Actions on push to main. |
| Backend (FastAPI + WebSocket) | **Render free tier** | Only real permanent free option with WebSocket support left (Fly.io/Railway dropped their free tiers in 2024–2026). Free tier spins down after inactivity — first request after idle takes ~30–60s to wake. Acceptable for a hobby project with sparse traffic. |
| CORS | Configure on backend | Frontend (GitHub Pages) and backend (Render) are different origins — enable CORS for the Pages domain, and allow it for the WebSocket handshake too. |

**Upgrade path if free tier's cold-start becomes annoying:** Render paid tier removes spin-down starting ~$7/month. No architecture changes needed — same single-instance, in-memory-state design works on both.

---

## 8. Claude Code usage estimate (for reference)

- Whole core-port project estimated at **~1–3M tokens total**, roughly **$75–250** in API-equivalent cost, across ~15–30 sessions. Phase 2/3 features would add to this incrementally.
- Frontend (built from scratch) is the biggest chunk; backend port is smaller since logic carries over directly.
- Start with **Claude Pro** ($20/mo) — plenty for a sessions-based hobby pace. Only consider Max or API pay-as-you-go if `/usage` shows you regularly hitting session limits.
- Use Sonnet for routine component/CRUD work, save Opus for trickier design calls (e.g., the timer redesign, the layering pass).

---

## 9. Quick checklist to resume with

**Core port**
- [ ] Set up FastAPI + python-socketio project skeleton with the layered structure (domain / service / transport / persistence / config)
- [ ] Port `data.py` game logic into the domain layer (pure, no framework imports)
- [ ] Replace `threading.Timer` with an `asyncio.Task`-based timer feeding the same single processing path as manual guesses (fixes bug #3 structurally)
- [ ] Define JSON event/payload shapes (replacing HTML-fragment emits)
- [ ] Write unit tests for the domain layer
- [ ] Scaffold Vue app (Vite + Pinia + Vue Router, hash mode)
- [ ] Build core components: login, lobby, image viewer, chat, tag lists, user list
- [ ] Wire Socket.IO client to Pinia store
- [ ] Write integration tests (join → ready → play → win/lose)
- [ ] Fix `SECRET_KEY` → env var (via Settings object), fix `room` NameError bug, fix name-uniqueness check

**Phase 2**
- [ ] Centralized config/settings
- [ ] `ImageSource` interface + e621 implementation
- [ ] User accounts (real user IDs, auth, WebSocket token auth)
- [ ] Persistent stats (DB schema, write path off `GameOver` event, read endpoints)

**Phase 3**
- [ ] `DerpibooruClient` wrapper, async, with retry/backoff and real error handling
- [ ] Live alias resolution via Derpibooru's tag API + local cache table

**Deployment**
- [ ] Deploy backend to Render (free tier), set CORS for Pages domain
- [ ] Deploy frontend to GitHub Pages via Actions, verify base path + hash routing
- [ ] Smoke test end-to-end on the live URLs
