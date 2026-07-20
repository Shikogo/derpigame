# Roadmap

What's left to build. The core game — domain, service, transport, and the Vue
frontend — is complete and playable end-to-end; see [`README.md`](README.md) for
the architecture and how to run it.

Rough order: config and persistence unblock everything else, and accounts must
land before stats so stats key off a real user ID rather than a session UUID.

## Config

Hardcoded values still live in code: `SECRET_KEY`, the default query, timer
duration, elimination threshold. Move them into a centralized Pydantic `Settings`
object in `app/config/`, injected rather than imported. `SECRET_KEY` in
particular must come from the environment before anything ships publicly.

## Persistence

There's no database. Round history and the win tally are in-memory service state
and are lost on restart. Needs `app/persistence/` repositories (SQLite is fine),
a schema, and a write path — the `GameOver` event is the clean hook point.

## Derpibooru client hardening

`app/service/derpibooru.py` is a real async client and already handles the
mandatory back-off rules (501 challenge → 5s, 500 block → 15min, others
exponential) and live tag-alias resolution with an in-memory cache. What's left:

- **Request spacing** to stay under the search-path limit of 20 requests per 10
  seconds when several rooms fetch at once.
- **Response caching that respects server-side expiry** (`Cache-Control` /
  `Expires`). This is required by the API license, not just an optimization.
- **A shared `AsyncClient`** with app-lifespan cleanup, for connection pooling,
  instead of constructing one per request.

Deferred by choice: a DB-backed alias cache and background refresh of stale
entries. Aliases rarely change and the cache is only lost on restart.

The API's rules are recorded in the `derpibooru-api-rules` memory — re-read them
before touching request behavior.

## e621 integration

Structurally similar to Derpibooru, behind the same `ImageSource` interface so a
room can pick its source. The domain needs no changes — all tag classification
already comes from the injected `TagTaxonomy`, so e621 is a new taxonomy constant
for its namespaces and rating vocabulary.

Specifics that will bite: e621 blocks generic User-Agents and requires a custom
one, and anything beyond anonymous search needs username + API-key auth.

## User accounts

The hardest piece, and it reshapes other decisions. Needs a users table with
persistent IDs replacing the throwaway per-session UUID, password hashing
(argon2/bcrypt) or OAuth — GitHub login suits this project — and token handling
that extends into WebSocket auth on connect.

## Persistent stats

Built on accounts and persistence: a schema for users/games/results, the write
path off `GameOver`, and read endpoints (`/stats/{user}`, `/leaderboard`).

## Deployment

Target: $0/month.

| Piece | Where | Notes |
|---|---|---|
| Frontend | GitHub Pages | Set Vite `base` and the router base to match. Hash mode avoids needing the `404.html` SPA-redirect trick. Deploy via Actions on push to main. |
| Backend | Render free tier | The remaining permanent free option with WebSocket support (Fly.io and Railway dropped theirs). Spins down when idle — first request after a lull takes ~30–60s. |
| CORS | Backend config | Pages and Render are different origins; allow the Pages domain for the WebSocket handshake too. |

If cold starts get annoying, Render's paid tier removes spin-down at ~$7/month
with no architecture change — the single-instance, in-memory design works on both.

## Deferred by choice

Settled decisions worth not relitigating without reason:

- **Automated integration/e2e tests.** Low ROI here; multiplayer flows are
  verified by a manual browser pass, with unit suites carrying the coverage.
- **Mid-game player removal.** An active player who disconnects simply times out
  and is eliminated over the threshold, rather than being cleanly removed.
- **Host authority.** Anyone in a room may start or configure it. Revisit
  alongside accounts.
- **Multi-instance state.** In-memory is deliberate. Redis and the Socket.IO
  Redis adapter only matter if more than one backend instance ever runs.
