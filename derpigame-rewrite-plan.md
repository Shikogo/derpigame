# Derpigame Rewrite Plan (Vue + API)

Remaking `derpigame-legacy` (Flask + Flask-SocketIO + server-rendered Jinja) into a modern Vue frontend backed by a proper API + WebSocket layer.

---

## 0. Status (updated 2026-07-19)

**The core rewrite is complete and playable end-to-end: the backend (domain /
service / transport) and the Vue frontend are both built and tested. Config
(Pydantic `Settings`) and persistence (a real DB) are the main unbuilt pieces —
round history and the win tally currently live in in-memory service state.**

Backend — done (**138 tests** + a live socket smoke test):
- **Domain** (`app/domain/`, pure — no framework imports): `Game`, `Room`,
  `User`, `Player`, `TagBucket`, `TagTaxonomy`, and the event objects
  (`app/domain/events.py`). Methods return event objects describing what
  happened; they never emit or render.
- **Service** (`app/service/`): `GameService` orchestration on a single event
  loop (fetch → mutate domain → emit → time), the `EventEmitter` ABC, the
  asyncio `TurnTimer` (bug #3 fixed structurally, see §3b), the `ImageSource`
  abstraction with a `StaticImageSource` for tests, `singledispatch`-based
  event→JSON serialization, and `GameActionError`/`NotYourTurn`. Also composes
  the **image payloads** the domain never sees (`image_started` at game start,
  `image_revealed` — artist/source/page attribution — at reveal) and keeps
  **in-memory round history + win tally** per room.
- **Transport** (`app/transport/`): the only layer importing FastAPI/socketio
  (and only its composition root `app.py` does — emitter/handlers take the server
  injected). `RoomRegistry` (replaces the legacy `rooms = {}` global), the real
  `SocketIOEmitter`, `room_state` snapshots, gfycat-style room codes
  (`room_codes.py`), and the full socketio handler set with `GameActionError` →
  per-caller ack. `create_app()` mounts `socketio.ASGIApp` on FastAPI; runnable
  via `uvicorn app.main:app`. Per-room settings (query / nsfw / **turn length**)
  flow through `configure_room`; a late/rejoining socket gets a game snapshot.
  Fixes bug #1 (clean `no_players_ready` ack) and bug #2 (real name-uniqueness).
- **Image source** (`app/service/derpibooru.py`): a minimal async
  `DerpibooruImageSource` (real `httpx` against the REST search API, not the legacy
  sync `derpibooru` package) — the default source in `create_app`, so the game is
  playable with real images. It honors Derpibooru's mandatory back-off rules via a
  cooldown gate (501 challenge → 5s, 500 block → 15min, other failures →
  exponential), and forces `https:` on image URLs. Retry/caching/alias are still
  Phase 3. An offline `dev_server:app` swaps in a `StaticImageSource` for
  token-free frontend work.

Frontend — done (**67 Vitest tests**, `vue-tsc` typecheck + `vite build` clean):
- Scaffolded with **Vite 8 + Vue 3.5 + Pinia + Vue Router 5 (hash mode) +
  TypeScript + Tailwind v4** (`@theme` tokens). (Note: built on Node 22 with the
  current Vite 8 / Tailwind 4 line, not the Node-18 / Vite-5 / Tailwind-3 pin the
  build plan first scoped.)
- Wire-contract types (`src/types/wire.ts`) mirror the backend snake_case JSON
  exactly — no case-translation layer — behind a thin typed `socket.io-client`
  wrapper with ack promises.
- Pinia stores over a **pure `(state, event) => state` reducer** (`game/reducer.ts`),
  the frontend analogue of the pure domain, so game state is unit-testable
  without mounting or a live socket.
- Full component set: home hero, lobby (roster / ready / settings dialog /
  invite link / round history), the live game (pan/zoom `ImageViewer`, turn
  indicator + circular countdown timer, the dedicated guess box — **not** chat —,
  per-type guess-feed badges, scoreboard, tag progress), the game-over screen
  with **mandatory attribution** (artist + source/page links, shown on both a
  finished and an aborted round), a social chat, and an **18+ age gate** for NSFW
  rooms.
- Dark-first "booru, gamified" visual identity: category-colored tag pills,
  self-hosted fonts, an accent image glow.
- The **per-turn time limit is configurable** in room settings.

Not started / deferred:
- **Config** (`app/config/`) — Pydantic `Settings`; `SECRET_KEY` / defaults
  (timer duration, elimination threshold, default query) still live in code.
- **Persistence** (`app/persistence/`) — no DB yet; history and the win tally are
  in-memory service state, lost on restart.
- **Automated integration / e2e tests** — deliberately skipped in favor of a
  manual browser pass; the backend + frontend unit suites carry the coverage.
- **Phase 2/3** (e621, accounts, stats, alias resolution) and **deployment**.

### Design refinements vs. the original plan

- **`TagTaxonomy` replaces per-source `TagType` tweaks.** Tag classification
  (namespaces, rating tags, ignored prefixes, goal bucket) is a data-driven
  value object injected into `Game`, with a Derpibooru default constant. Adding
  e621 (Phase 2, item 2) becomes a new taxonomy constant with **zero domain
  changes** — the magic prefix handling that would have needed per-source edits
  is gone.
- **Two outbound channels, not one.** Room-wide state flows through the
  `EventEmitter` (broadcast to the room). Per-caller rejections are *raised* as
  `GameActionError`/`NotYourTurn` for the transport to turn into a socketio ack
  to that one caller — never broadcast, so other clients don't see a spurious
  correction.
- **Only the active player may guess.** Frontend gates the input; the backend
  enforces it as the authority (raising `NotYourTurn` otherwise).
- **Behavior cleanups over legacy:** the dead `incorrect_guesses` state became a
  live `failed_guesses` set; a repeated wrong guess is a no-op (no double
  penalty); blank/whitespace guesses are ignored (no strike); `Game.start()` is
  idempotent.
- **Rooms are invite-code rooms, not typed names.** `create_room` mints a
  gfycat-style code (`spunky-lucky-griffon`); `join_room` requires an *existing*
  code (`room_not_found` otherwise), so unrelated groups can't collide on a name
  and rooms are private-by-default behind their link. This retires the legacy
  `nsfw`-prefix hack — nsfw/query are room config set at creation. `stop_game`
  (legacy `!stop`) is kept; host authority is open (anyone may start/configure
  for now).

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

1. **Crash in `Room.start_game`**: `say("No players are ready!", room, 'status')` — `room` isn't defined in scope, should be `self.name`. Throws `NameError` if "start" is hit with zero ready players. **✅ Fixed:** the port has no such method; the transport's `start_game` handler returns a clean `no_players_ready` ack when nobody's ready.
2. **Broken uniqueness check** in `forms.py`: `unique_name_check` compares a string against `User` objects (`field.data in sessions.values()`), which is always `False` since `User` has no `__eq__`. Username uniqueness is currently a no-op. **✅ Fixed:** the `join_room` handler does a real case-insensitive name check against the room's users, returning `name_taken`.
3. **Race condition** between guess submission and turn timeout: `game.timer.cancel()` doesn't guarantee the timeout callback isn't already mid-execution on its own thread. No lock protects `self.players` — worst case, double turn-advance or corrupted game state. Root cause is architectural (see §3b) — the real fix is removing the second thread, not just adding a lock. **✅ Fixed:** replaced by the single-loop asyncio `TurnTimer`, whose generation counter drops any superseded fire. No second thread, so the whole race category is gone.
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
| **Domain** (`Game`, `Room`, `User`, `TagTaxonomy`) | Pure game rules. Methods take input, return an event object describing what happened (`CorrectGuess`, `WrongGuess`, `PlayerEliminated`, `GameOver`) — no `emit()`, no `render_template()`, no socketio/Flask imports at all. Source-specific tag classification lives in an injected `TagTaxonomy` value object, not in `Game`. | Nothing but the standard library |
| **Application/service** | Orchestrates domain objects; calls the `ImageSource` abstraction (Derpibooru/e621) and persistence (stats, alias cache); turns domain result objects into outbound event data | Domain layer, `ImageSource`, repositories |
| **Transport** (FastAPI + socketio handlers) | Thin adapters only: parse the incoming socket/HTTP message, call the service layer, take the returned event(s), serialize to JSON, emit | Application layer |
| **Persistence** (repositories) | DB access for users, stats, alias cache — swappable/mockable, not called directly from domain code | DB / SQLite |
| **State/session store** | Replaces the global `rooms = {}` / `sessions = {}` module-level dicts with an injected store class (in-memory now, Redis-backed later without touching callers) | — |
| **Config** | Centralized `Settings` object (Pydantic Settings), injected — replaces scattered hardcoded constants | — |

**Why this matters beyond tidiness:**
- **Testability**: domain layer has zero framework dependencies, so unit tests (already planned in Phase 1) can run in milliseconds with no app context, no mocking `emit()`.
- **Fixes bug #3 structurally**: the turn timer becomes an `asyncio.Task` that, on expiry, feeds a "timeout" event through the *same* single-threaded processing path as a manual guess — there's no longer a second thread that can race with the main flow, so the whole bug class disappears rather than being patched with a lock.
- **Sets up every Phase 2/3 feature cleanly**: persistent stats hook in as another consumer of domain result objects (no change to game logic); the `ImageSource` abstraction for e621 sits cleanly in the service layer; alias caching is just another repository.

### 3c. Transport contract (as built)

The transport is the only layer that imports FastAPI/socketio (and only its
composition root `app.py` does — `SocketIOEmitter` and `SocketHandlers` take the
server injected). It runs as an ASGI app (`socketio.ASGIApp` mounted on FastAPI)
on a **single event loop** — the same loop the `TurnTimer` uses, which is what
keeps turn advancement race-free. Its whole job: identify a socket, look up the
`Room`, call `GameService`, and translate results back. It holds **no game
logic**.

**Identity & connection.** No real auth yet (Phase 2). The client generates a
`uuid` once and stores it (localStorage), so a reconnect re-presents the same
identity — this is the stable key Phase 2 accounts/stats will replace. On
`create_room`/`join_room` the server records `{uuid, room, name}` in the socket
session (`sio.save_session`) and joins the socket to the **socketio room named
after the room code**, so a room broadcast is just `sio.emit(..., room=code)`.

**Rooms are invite codes.** `create_room` mints a gfycat-style code
(`room_codes.py`, e.g. `spunky-lucky-griffon`); `join_room` requires an existing
code. Shared via an invite link (`#/room/<code>` under the frontend's hash
router). This drops the legacy `nsfw`-prefixed room-name hack.

**State store.** A `RoomRegistry` (injected, in-memory now — Redis-backed later
per §3b) replaces the legacy global `rooms = {}`: `create(name)` (fails on
collision, so minting retries), `get(name)`, `remove(name)`. `GameService`
methods already take a `Room`, so the transport resolves one from the registry
and passes it in.

**Client → server** (every message takes a socketio **ack callback** for the
per-caller reply; room-wide effects broadcast separately):

| Event | Payload | Does | Ack to caller |
|---|---|---|---|
| `create_room` | `{name, uuid, nsfw?, query?}` | mint a code, `registry.create`, apply config, join creator | `{ok, room_state}` |
| `join_room` | `{room, name, uuid}` | `registry.get` (else `room_not_found`), name-uniqueness check (else `name_taken`), `room.add_user`, join socketio room | `{ok, room_state}` / `{ok:false, error}` |
| `set_ready` | `{ready}` | toggle `user.ready` | `{ok}` |
| `configure_room` | `{query, nsfw}` | update room search config (pre-game only) | `{ok}` / `{ok:false, error}` |
| `start_game` | `{}` | `GameService.start_game(room)` (else `no_players_ready` / `game_in_progress`) | `{ok}` / `{ok:false, error}` |
| `submit_guess` | `{guess}` | `GameService.submit_guess(room, uuid, guess)` | `{ok}` or `{ok:false, error:"not_your_turn", active_player}` |
| `stop_game` | `{}` | `GameService.stop_game(room)` — abort a live game, back to lobby | `{ok}` |
| `leave_room` | `{}` | `room.remove_user`, leave socketio room, tear down if empty | `{ok}` |
| `chat` | `{text}` | broadcast only — **never touches the game** | `{ok}` |

Disconnect is treated as `leave_room`.

**Server → client** — three channels:
- **`game_events`** — the domain/service broadcast family, emitted as one batched
  list of typed payloads (`game_started`, `turn_started`, `correct_guess`,
  `wrong_guess`, `timeout`, `player_eliminated`, `guess_rejected`, `game_over`,
  plus the service's `no_image` / `image_error` / `game_aborted`). The real `EventEmitter` is a
  one-liner: `SocketIOEmitter.emit(room, payloads)` → `sio.emit("game_events",
  payloads, room=room)`. The client owns a reducer that switches on `type`.
- **`room_state`** — a full lobby snapshot (roster with names/ready flags, query,
  nsfw, `in_progress`) rebroadcast on any membership/config change. Whole-snapshot,
  not diffs — simplest for the client and cheap at this roster size.
- **ack callbacks** — per-caller replies (including `GameActionError`
  translations); never broadcast.

**Decision — lobby events aren't domain events.** Membership/readiness/config
changes aren't game rules, so they stay out of the pure domain (`Room.add_user`
& co. return no events, by design). The transport composes the `room_state`
snapshot from `Room` after a lobby mutation and broadcasts it. Only *game*
actions flow through `GameService` + the emitter. This keeps the domain pure and
avoids inventing a parallel lobby-event vocabulary.

**Error translation.** Transport wraps service calls in a `try/except
GameActionError`, returning `{ok:false, error, ...}` in the ack — `NotYourTurn`
carries the `active_player` so the client can reconcile. Only exceptions become
acks; room state only ever moves through the emitter.

**Edge cases — decided while building:**
- *Active player disconnects mid-turn:* their turn simply times out (they stay a
  `Player`; the turn timer eliminates them over the threshold). Clean mid-game
  player removal in the domain is deferred.
- *Host authority for `start`/`configure`:* anyone in the room, no host role yet
  (revisit with Phase 2 accounts).
- *Empty-room cleanup:* immediate — the last user leaving cancels the room's turn
  timer (`GameService.cancel_room`) and drops it from the registry.

---

## 4. Build phases

1. ✅ **Backend API + WebSocket layer** — port `data.py` game logic into the layered structure above (domain / service / transport), replace HTML-fragment emits with JSON, fix bug #2 (real name-uniqueness check) and bug #3 (timer race, via the asyncio-task redesign) along the way.
2. ✅ **Unit tests** — cover the domain layer in isolation (turn order, elimination, fuzzy-match scoring, tie detection) — no app context needed given the layering above. Done for the backend, and mirrored on the frontend (Vitest over the pure reducer, viewer geometry, stores, and the gating components).
3. ✅ **Vue frontend** — components for login, room/lobby, image viewer, a dedicated
   guess input, correct/incorrect guess badges, user list, score display. Pinia
   store for room/game state. **The game no longer happens in the chat** (unlike
   legacy): guesses go through a purpose-built input box, and correct/incorrect
   guesses render as badges/pills driven by the domain events (`CorrectGuess`,
   `WrongGuess`, etc.), not chat lines. A chat may still exist, but purely as a
   social side-channel — never the place guesses are submitted or scored.
   **Attribution is mandatory** (Derpibooru license): the image viewer must credit
   the artist (`artist:*` tags) and show the source URL alongside the image once a
   game ends / the image is revealed; a link to the derpibooru.org page is
   recommended; all URLs must be `https:`. (Care: don't reveal artist/source tags
   mid-game — they'd give away answers.)
4. ⏭️ **Integration tests** — deliberately skipped: automated integration/e2e (a full transport or browser drive of join → ready → start → guess → win/lose) is low-ROI here, so this flow is verified by a manual browser pass instead. The backend and frontend unit suites carry the automated coverage.
5. **Bugfixes** — #1 (`room` → `self.name`) ✅ done; #4 (`SECRET_KEY` env var) deferred to the config step (no auth yet).
6. **New features** — see Phase 2/3 below (not started). Extras landed during the core port: per-room configurable turn length, round history + win tally, dark-first visual identity, and the NSFW age gate.

---

## 5. Phase 2 — extended features (after core port is stable)

Suggested order matters here — accounts before stats, since stats should key off a real user ID rather than a throwaway session UUID.

1. **Better config** — easiest. Move hardcoded values (`SECRET_KEY`, default query, timer duration, elimination threshold) into a centralized `Settings` object (see §3b), expose relevant bits through the API for room-level config instead of just the query textbox.
2. **E621 integration** — easy-to-moderate. Structurally similar to Derpibooru (booru-style JSON API). Specifics: requires a custom User-Agent header (e621 blocks generic ones), username+API-key auth for anything beyond anonymous search, and a different tag/rating vocabulary than Derpibooru's — supply an e621 `TagTaxonomy` constant for its namespaces/rating tags (the domain already reads all classification from the injected taxonomy, so no `Game` changes). Implement behind the same `ImageSource` interface as Derpibooru so rooms can pick a source.
3. **User accounts** — hardest, reshapes other decisions. Needs a `users` table with persistent IDs (replacing the throwaway per-session UUID), password hashing (bcrypt/argon2) or OAuth (GitHub login fits this project well), and token/session handling that extends into WebSocket auth on connect.
4. **Persistent stats** — moderate, built on top of accounts. Needs a database (SQLite is fine), a schema for users/games/results, a write path when `Game` emits its `GameOver` result object (see §3b — this is a clean hook point), and new read endpoints (`/stats/{user}`, `/leaderboard`).

---

## 6. Phase 3 — Derpibooru improvements

**API handling** (~a day, mostly plumbing). *A minimal async source already
exists* (`app/service/derpibooru.py`, §0) — this phase hardens it:
- ✅ Already done: async `httpx` calls straight against the REST API (no sync
  `derpibooru` package), a clean `ImageSourceError` → in-room error message, and a
  mandatory back-off gate (501 challenge → 5s, 500 block → 15min, other failures →
  exponential) so we can't get IP-banned. The docs' rules live in the
  `derpibooru-api-rules` memory.
- Still to do: request-spacing to stay under the search-path limit (20 req/10s)
  when many rooms fetch at once; response **caching that respects server-side
  expiry** (`Cache-Control`/`Expires`) — required by the API license; a shared
  `AsyncClient` (connection pooling) with app-lifespan cleanup instead of a client
  per request.

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
- [x] Layered structure laid out (domain / service / transport / persistence / config); FastAPI + python-socketio wired via `create_app()` / `uvicorn app.main:app`
- [x] Build the transport per **§3c**: `RoomRegistry`, socketio handlers (create / join / ready / configure / start / guess / stop / leave / chat), `SocketIOEmitter`, `room_state` snapshots, gfycat-style room codes, `GameActionError` → ack
- [x] Port `data.py` game logic into the domain layer (pure, no framework imports)
- [x] Replace `threading.Timer` with an `asyncio.Task`-based timer feeding the same single processing path as manual guesses (fixes bug #3 structurally)
- [x] Define JSON event/payload shapes (replacing HTML-fragment emits) — `singledispatch` serializers
- [x] Write unit tests for the domain layer (plus service + transport — 138 tests) and an end-to-end socket smoke test
- [x] Scaffold Vue app (Vite + Pinia + Vue Router, hash mode)
- [x] Build core components: login, lobby, image viewer, guess input box, correct/incorrect guess badges, user list, chat (social-only — not the guess path), plus game-over attribution, round history, circular turn timer, and the NSFW age gate
- [x] Wire Socket.IO client to Pinia store (thin typed client + a pure `(state, event) => state` reducer; 67 Vitest tests)
- [x] End-to-end flow verified manually in the browser (automated integration/e2e intentionally skipped — see phase 4)
- [x] Fix `room` NameError bug (bug #1 — zero-ready start now a clean ack) and name-uniqueness check (bug #2)
- [ ] Fix `SECRET_KEY` → env var (via Settings object) — deferred to the config step (no auth yet)

**Core port**
- [x] Minimal async Derpibooru `ImageSource` (`app/service/derpibooru.py`) — real `httpx`, back-off gate honoring the API rules, wired as the `create_app` default

**Phase 2**
- [ ] Centralized config/settings
- [x] `ImageSource` interface (Derpibooru/e621-swappable, with `StaticImageSource` for tests)
- [ ] e621 `ImageSource` implementation + e621 `TagTaxonomy`
- [ ] User accounts (real user IDs, auth, WebSocket token auth)
- [ ] Persistent stats (DB schema, write path off `GameOver` event, read endpoints)

**Phase 3**
- [~] `DerpibooruClient` wrapper, async, with retry/backoff and real error handling
- [ ] Live alias resolution via Derpibooru's tag API + local cache table

**Deployment**
- [ ] Deploy backend to Render (free tier), set CORS for Pages domain
- [ ] Deploy frontend to GitHub Pages via Actions, verify base path + hash routing
- [ ] Smoke test end-to-end on the live URLs
