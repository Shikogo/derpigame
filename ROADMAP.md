# Roadmap

What's left to build. The core game — domain, service, transport, and the Vue
frontend — is complete and playable end-to-end; see [`README.md`](README.md) for
the architecture and how to run it.

Rough order: persistence unblocks the rest, and accounts must land before stats
so stats key off a real user ID rather than a session UUID.

## Persistence

There's no database. Round history and the win tally are in-memory service state
and are lost on restart. Needs `app/persistence/` repositories (SQLite is fine),
a schema, and a write path — the `GameOver` event is the clean hook point.

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
| Backend | Render free tier, or Fly.io auto-suspend | Render is the simplest permanent free option with WebSocket support, but spins down when idle — first request after a lull takes ~30–60s. Fly.io (see below) trades a little setup for a much faster wake. |
| CORS | `DERPIGAME_SERVER__CORS_ORIGINS` | Pages and the backend are different origins; allow the Pages domain for the WebSocket handshake too. It defaults to `["*"]`, so this must be narrowed before shipping. |

If Render's cold starts get annoying, its paid tier removes spin-down at
~$7/month with no architecture change — the single-instance, in-memory design
works on both.

### Fly.io backend (alternative)

Fly no longer has a blanket free tier, but a metered pay-as-you-go machine that
idles to near-zero fits a bursty party game well. Needs a `Dockerfile` for the
FastAPI + socketio app and a `fly.toml` — neither exists yet.

Shape:

- **A single `shared-cpu-1x` machine** (256–512 MB is plenty; state is in
  memory, not large). No persistent volume — the in-memory design means there's
  nothing to mount, which also keeps the footprint minimal.
- **Auto-suspend, not auto-stop.** `auto_stop_machines = "suspend"` with
  `min_machines_running = 0`. Suspend snapshots RAM and resumes in well under a
  second, versus a multi-second cold boot for `"stop"` and ~30–60s on Render.
  For this app that's a correctness win as much as a speed one: the snapshot
  keeps live room state alive across an idle gap instead of losing it to a
  restart. A live game holds open sockets, so it won't suspend mid-round.
- **Bandwidth is the only real variable.** Metered compute for a game that's
  live only tens of hours a month is pennies; egress is what can move. Loading
  Derpibooru images client-side (browser → Derpibooru CDN) keeps backend egress
  near zero. If the hardened image client ever proxies images through the
  server, egress scales with their size — booru originals run to tens of MB
  each — so that choice, not the compute, is what to watch.

Single-instance only, same as Render — suspend preserves the in-memory state
that a multi-instance setup would otherwise force into Redis (see below).

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
