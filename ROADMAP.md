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

## Rating via caps; filter for content only

Rating is gated in two places at once: a room's `rating_caps` (soft, `-tag`
exclusions) and the source filter (hard, server-side), with the NSFW toggle
switching between a source's SFW and NSFW `filter_id`. The effective ceiling is
the *min* of the two, which is opaque — a host can raise a cap and see nothing
change because the filter still blocks it.

The plan: make the filter a pure **content** policy (block AI, junk, and other
never-wanted tags) and let `rating_caps` own rating outright — one
rating-permissive base filter per source, no SFW/NSFW split. The NSFW toggle
stays as the statement of intent, but instead of switching filters it clamps
*which cap levels are selectable*, enforced server-side in the handler so it
stays a real floor, not just a UI hint.

Both sources already have a fitting base filter: Derpibooru's `232619` and a
custom Furbooru filter `12153` (blocks AI/drama/politics, rating-permissive, and
public so the anonymous client applies it). So no AI-exclusion mechanism is
needed.

Decisions to settle:

- **SFW ceiling** — cap at `safe` on both (consistent with today's default) or
  per-source? Does the toggle gate the darkness axis too, or only rating?
- **Config** — collapse `default_filter_id`/`nsfw_filter_id` to one `filter_id`
  per source; add the nsfw→ceiling mapping.
- **Frontend** — the settings dialog re-filters the cap dropdowns by the NSFW
  toggle live; a small wire addition so the server states the per-nsfw ceiling.

Tradeoff to accept: with the filter no longer gating rating, an SFW room's safety
rests entirely on the server-side cap clamp — more transparent, but one fewer
hard backstop, so the clamp wants thorough tests.

## User accounts

The hardest piece, and it reshapes other decisions. Needs a users table with
persistent IDs replacing the throwaway per-session UUID, password hashing
(argon2/bcrypt) or OAuth — GitHub login suits this project — and token handling
that extends into WebSocket auth on connect.

## Persistent stats

Built on accounts and persistence: a schema for users/games/results, the write
path off `GameOver`, and read endpoints (`/stats/{user}`, `/leaderboard`).

## Custom domain

`derpigame.shikogo.com` for the Pages frontend. The backend already allows the
origin — `fly.toml` lists it beside the Pages one — so this needs the DNS record
and the Pages setting, plus Vite's `base` dropping from `/derpigame/` to `/`,
since a custom domain serves from the root rather than a project subpath.

## Deferred by choice

Settled decisions worth not relitigating without reason:

- **Mid-game player removal.** An active player who disconnects simply times out
  and is eliminated over the threshold, rather than being cleanly removed.
- **Host authority.** Anyone in a room may start or configure it. Revisit
  alongside accounts.
- **Multi-instance state.** In-memory is deliberate. Redis and the Socket.IO
  Redis adapter only matter if more than one backend instance ever runs.
