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
```

Both halves should be clean before a commit. Nothing runs these automatically —
there's no CI or pre-commit hook yet, so they're manual for now.

## What each tool covers

| Tool | Scope | Catches |
| --- | --- | --- |
| ruff | `backend/` | Lint + import sorting + formatting, and the domain layering rule |
| pytest | `backend/` | Domain rules, service orchestration, transport handlers |
| ESLint | `frontend/` | JS/TS correctness + Vue template rules (`v-for` keys, etc.) |
| Prettier | `frontend/` | Formatting |
| vue-tsc | `frontend/` | Types, including inside `.vue` SFCs |
| Vitest | `frontend/` | The pure reducer, stores, and components |

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
- **No e2e suite.** Multiplayer flows are verified by hand in the browser — open
  two tabs, or see the hosting section in the README. Unit tests still cover new
  logic on both sides. Playwright is a devDependency, but as a way to drive a
  headless browser when a change needs *looking* at — a phone-width layout, a
  before/after screenshot diff — not as a test suite to grow. Nothing in `npm
  run test` touches it.
