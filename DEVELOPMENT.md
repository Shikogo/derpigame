# Development checks

The quality gate for this repo, in one place. See [`README.md`](README.md) for
setup, running the app, and the architecture tour.

## Running everything

Backend, from `backend/`:

```bash
.venv/bin/ruff check app tests      # lint (includes the layering rule below)
.venv/bin/ruff check --fix app tests
.venv/bin/ruff format app tests     # format
.venv/bin/python -m pytest          # tests
```

Frontend, from `frontend/`:

```bash
npm run lint          # ESLint
npm run lint:fix
npm run format        # Prettier, in place
npm run format:check  # Prettier, report only
npm run typecheck     # vue-tsc -b
npm run test          # Vitest
npm run e2e           # Playwright — starts both servers itself
```

`npm run e2e` needs the backend venv in place: it launches
`backend/dev_server.py` alongside Vite and drives the pair. Servers already
running (`./run-local.sh --offline`) are reused rather than duplicated.

The Node version lives in [`.nvmrc`](.nvmrc) at the repo root — `nvm use` picks
it up from either directory, and CI reads the same file rather than pinning a
number of its own.

Both halves should be clean before a commit. GitHub Actions runs the same set on
every push to `main` and every pull request
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)), but there's no
pre-commit hook — locally they're still yours to run, and CI is the backstop
rather than the first place you find out.

CI uses `ruff format --check` and `npm run format:check` in place of the
in-place commands above; everything else is identical.

**The deploys gate on the same suite, in the same run.** `ci.yml` holds the
whole graph: the two unit jobs, the e2e job, and the deploys hanging off them as
`needs:`. So a red `main` doesn't ship — the Fly deploy waits on the backend
suite, the Cloudflare Pages deploy on the frontend one, and each ignores the
other half so an unrelated failure can't block a fix.

That gate is the reason the frontend deploys through `wrangler` from this
workflow rather than through Cloudflare's own Git integration: Cloudflare builds
on push without seeing a test result, so connecting the repo there would put a
second, ungated path to production alongside this one.

The e2e job is the one place a half blocks on the other: *both* deploys need it.
A frontend that can't play a round through — or a backend that can't carry one —
shouldn't ship because its own half was green. It costs about a minute.

It's a single workflow because a called workflow is expanded once per caller,
with no sharing between runs. Split across a checks workflow and two deploy
workflows, a push touching both halves ran the e2e suite three times over.

A `changes` job decides which deploys run, keeping a frontend-only push from
restarting the backend machine and dropping the rooms it's holding. A manual run
(`workflow_dispatch`) has no diff to work from and takes the two booleans
instead.

Every branch runs the workflow, because a branch push publishes a Cloudflare
preview at `<branch>.derpigame.pages.dev` — the same build the production deploy
would make, at a URL of its own. What separates the two is the `--branch`
wrangler is handed: Cloudflare calls a deploy production only when it names the
project's production branch, so that setting must stay `main`. The Fly deploy
has no such split — one machine, no preview — so it carries an explicit `main`
gate to keep a branch push away from it. A preview points at the *production*
backend, so rooms are shared with live players rather than isolated.

Nothing is a *required status check* on `main` by choice: those only pass for
commits GitHub has already seen, which would mean pushing a branch and waiting
before every one-line fix. Gating the deploys protects what actually matters
without changing how you commit.

## What each tool covers

| Tool | Scope | Catches |
| --- | --- | --- |
| ruff | `backend/` | Lint + import sorting + formatting, and the domain layering rule |
| pytest | `backend/` | Domain rules, service orchestration, transport handlers |
| ESLint | `frontend/` | JS/TS correctness + Vue template rules (`v-for` keys, etc.) |
| Prettier | `frontend/` | Formatting |
| vue-tsc | `frontend/` | Types, including inside `.vue` SFCs |
| Vitest | `frontend/` | The pure reducer, stores, and components |
| Playwright | both | A round end to end, and two players sharing a turn |

Formatting and correctness are kept in separate tools that never overlap:
`eslint-config-prettier` runs last in the ESLint config and drops any rule that
would argue with Prettier. So ESLint findings are always real problems, never
layout opinions — don't add layout rules back.

ESLint and `vue-tsc` also divide cleanly: ESLint doesn't type-check, and
`vue-tsc` can't see template semantics. Both are worth running.

Use `npm run typecheck`, never `tsc --noEmit` — this is a project-references
build, so `--noEmit` checks nothing and exits 0.

## The domain layering rule

`CLAUDE.md` and the README both state that `app/domain/` is pure game rules: no
framework imports, no I/O, and no reaching "up" into the layers that orchestrate
it. That rule is **enforced**, not just documented — ruff's banned-imports config
in `backend/pyproject.toml` fails the lint if `domain/` imports FastAPI, socketio,
starlette, uvicorn, an HTTP client, settings, or any of `app.service`,
`app.transport`, `app.persistence`, `app.config`.

The ban is scoped to `domain/` by a negated glob in `per-file-ignores`; every
other layer may import freely. To add a newly-banned module, extend the
`[tool.ruff.lint.flake8-tidy-imports.banned-api]` table.

If you hit this error, the fix is almost never to add an ignore — it's that the
logic belongs in `service/` instead.

## Formatting conventions

Both formatters are configured to match the code that already existed rather
than impose their defaults:

- **Line width 100** on both sides. Ruff's default (88) and Prettier's (80) both
  caused *more* churn than 100 when measured against the existing code.
- **No semicolons, single quotes** in the frontend (`.prettierrc.json`). The
  codebase was already written this way; Prettier's defaults are the opposite and
  would have rewritten every line for nothing.

Prettier occasionally breaks a Vue interpolation across lines when a tag exceeds
the print width, i.e. `>{{` / `}}<`. Where that hurts, put the interpolation on
its own line inside the element — that's stable under reformatting.

## Deliberate choices

Worth knowing so they don't get "fixed" later:

- **ESLint uses `eslint-plugin-vue`'s `essential` tier**, not `recommended`. The
  higher tiers are layout rules (one attribute per line, tag newlines) that
  duplicate and contradict Prettier.
- **`vue/multi-word-component-names` is off.** It guards against shadowing real
  HTML elements; names like `Scoreboard` don't collide.
- **The e2e suite stays small.** `frontend/e2e/` covers what only a real socket
  can show: a round played to its results screen, one guess of each verdict, and
  two players taking turns. It runs against `backend/dev_server.py`, whose images
  carry a known tag list — without that fixture a round's outcome depends on
  whatever the booru returned, and there'd be nothing to assert. Everything
  provable without a browser stays a unit test, which is most of it. `npm run
  test` doesn't touch Playwright; `npm run e2e` is its own command, and its own
  CI job, because it needs both halves of the repo installed.
