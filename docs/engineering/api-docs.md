---
id: DOC-008
type: api-docs
status: draft
phase: null
owner: james
tags: [backend]
links: [DOC-007]
updated: 2026-07-22
---

# API reference

> **Populate from the actual code**, not from memory. The router groups below are real
> (registered in `backend/app/main.py`), but the per-route details are deliberately left
> blank rather than guessed.
>
> There is also a live interactive reference: the backend serves Swagger at `/docs`,
> which is generated from the code and therefore never stale. **This file exists for
> the things Swagger cannot tell you** — why a route exists, what it costs, and what it
> is safe to call. If you find yourself duplicating Swagger here, stop.

## How to fill a row

| Field | Meaning |
|---|---|
| Method / Path | As registered on the router |
| Auth | Does it require a valid token? Rate limited? |
| Inputs | Body/query params that matter, not every field |
| Outputs | Shape of the success response |
| Notes | Side effects, cost, danger. **This is the column worth writing.** |

## Router groups

| Prefix | Module | Purpose |
|---|---|---|
| `/portfolio` | `routes/portfolio.py` | Account-level view, snapshots, metrics |
| `/trades` | `routes/trades.py` | Trade history, summary, export |
| `/run`, `/bot` | `routes/bot.py` | Manual cycle trigger, bot status |
| `/portfolios` | `plans/routes.py` | Portfolio CRUD, per-portfolio run, export |
| `/backtest` | `backtest/routes.py` | Backtest config CRUD + background run |
| `/earnings` | `earnings/routes.py` | Earnings calendar, refresh |
| `/screener` | `screener/routes.py` | Latest ranked candidates, refresh |
| `/forex` | `forex/routes.py` | Siloed forex backtester |
| `/company` | `company.py` | Cached company profile (backs ticker hover cards) |
| `/admin/todos` | `routes/todos.py` | Admin todo CRUD |

## Routes

<!-- One row per route. Start with the ones that MUTATE state or cost money — those are
     the ones worth documenting. Read-only GETs can lean on Swagger. -->

| Method | Path | Auth | Inputs | Outputs | Notes |
|---|---|---|---|---|---|
| POST | `/run` | required | TODO | TODO | Rate limited 2/min. Triggers a real trading cycle. |
| POST | `/portfolios/{id}/run` | required | TODO | TODO | Rate limited. Runs one portfolio. |
| PATCH | `/portfolios/{id}` | required | TODO | TODO | `{is_active: false}` is the kill switch. |
| TODO | | | | | |

## Cross-cutting behaviour

- **Rate limiting:** slowapi — 2/min on run endpoints, 60/min global default.
- **Auth:** Bearer token, ES256, verified via Supabase JWKS. `ALLOWED_EMAIL` accepts a
  comma-separated list.
- **Timeouts:** frontend uses 15s for most calls, 45s for `runPlan` because the model
  call is slow.

## TODO

- TODO — document error response shapes; are they consistent across routers?
- TODO — note which endpoints are safe to call repeatedly and which have side effects.
