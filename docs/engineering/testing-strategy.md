---
id: DOC-010
type: testing
status: active
phase: null
owner: james
tags: [testing, backend, frontend, database]
links: [DOC-007]
updated: 2026-07-22
---

# Testing strategy

## What we test

| Layer | Tool | Approach |
|---|---|---|
| Backend | pytest | SQLite in-memory (`StaticPool`) + FastAPI `TestClient` |
| Frontend | Vitest | `@testing-library/react` + jsdom |
| Gate | pre-commit hook | tsc + eslint + pytest + vitest on every commit |
| CI | GitHub Actions | on push/PR to `main` |

Markers: `unit`, `integration`, `e2e`. Helpers `make_plan()` and `make_trade()` live in
`tests/conftest.py`.

## Counts — and a warning about them

**Verified 2026-07-22: 405 backend tests passing.** Frontend not re-run this session.

Treat every other number you find as suspect. The count is currently written down in at
least four places that disagree:

| Source | Claims |
|---|---|
| `CLAUDE.md` testing section | 511 total (382 backend + 129 frontend) |
| `CLAUDE.md` commands section | 400 backend, 138 frontend |
| `/testing` page in the app | 535 |
| Measured by running the suite | 405 backend |

**This is exactly the class of number that should be generated, never hand-written.**
`npm run docs:refresh` (Step 6) computes it from the repo so the figure has one source.
Until then, do not trust a test count you did not just measure.

## How we test

- **Real code over mocks.** Mock only what is unavoidable: external HTTP, the broker,
  and the clock.
- **Scheduler is patched out** in the TestClient fixture, or it raises
  `SchedulerAlreadyRunningError`.
- **Recharts is mocked** in component tests — jsdom cannot render SVG.
- **Budget validation is stubbed** in integration tests, because `pg_advisory_xact_lock`
  is PostgreSQL-only.

## Ugly cases

The failures that actually cost time. Add to this list every time one bites.

- **SQLite tolerates what Postgres rejects.** A `numpy.float64` passed straight through
  SQLite and crashed Postgres in production. The whole suite was green. Any test touching
  numeric types is only as trustworthy as the database it ran against.
- **Local Python differs from production.** The `pandas_ta` `.ta` accessor is broken
  under the local Python build, so indicator tests mock `_compute_indicators`. That means
  those code paths are *not* exercised locally.
- **`python` on PATH is not the project interpreter.** Use `backend/venv/bin/python`.
- **Failures that need a live rate-limited API.** The snapshot `$0`-price bug could not
  be reproduced with a healthy mock — the mock always returned complete data. Tests that
  only simulate success will not catch a partial-failure bug.
- TODO — add the next one that bites.

## Gaps worth closing

- TODO — no test runs against real Postgres; the SQLite divergence above is unguarded.
- TODO — no test asserts that a scheduled cycle actually persisted a row, which is how
  the 13-day silent outage went unnoticed.
- TODO — frontend count unverified; re-run and record.
