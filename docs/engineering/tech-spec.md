---
id: DOC-007
type: tech-spec
status: active
phase: null
owner: james
tags: [backend, frontend, deployment, database]
links: [ADR-001, DOC-008]
updated: 2026-07-22
---

# Technical specification

## Architecture overview

A monorepo deploying **two independent Railway services** from the same GitHub repo.

```
                    ┌──────────────────────────────┐
   browser ────────▶│  Frontend — Next.js 14       │
                    │  App Router, standalone      │
                    └──────────────┬───────────────┘
                                   │ Bearer token (ES256 JWT)
                                   ▼
                    ┌──────────────────────────────┐
                    │  Backend — FastAPI           │
                    │  verifies JWT via JWKS       │
                    └───┬───────────┬───────────┬──┘
                        │           │           │
              ┌─────────▼──┐  ┌─────▼─────┐  ┌──▼──────────────┐
              │ Supabase   │  │  Alpaca   │  │ Anthropic       │
              │ Postgres   │  │  broker + │  │ Claude Sonnet   │
              │ + Auth     │  │  market   │  │ (decisions)     │
              └────────────┘  │  data     │  └─────────────────┘
                              └───────────┘
                                   +  Alpha Vantage (news)
                                      Finnhub (earnings, profiles)
```

### Request flow — a user action

1. Browser holds a Supabase session; `AuthProvider` pushes the token into the API layer.
2. Every call goes through `fetchAPI()` with a Bearer token and a 15s timeout.
3. FastAPI verifies the ES256 JWT against Supabase's JWKS endpoint, then checks the
   caller against the `ALLOWED_EMAIL` list.
4. The route reads or writes Postgres through SQLAlchemy and returns JSON.

### Data path — an automated trading cycle

This is the path that matters. It runs on a schedule, with no user present.

```
APScheduler fires (10:00 AM ET, and 3:30 PM ET exit-only)
   │
   ├─ gather      positions + balances (Alpaca), quotes, news, indicators,
   │              earnings, sector signals, optional screener feed
   ├─ decide      branch on decision_mode:
   │                claude_decides              → Claude returns all decisions
   │                rules_decide                → strategy signals only
   │                rules_with_claude_oversight → signals, then Claude reviews each
   ├─ coerce      qty<=0 or price<=0 → hold, reason preserved
   ├─ validate    per-portfolio constraints, budget, cross-portfolio sell protection
   ├─ act         submit orders to Alpaca
   └─ log         write EVERY decision to Postgres — holds and blocked trades included
```

Two scheduled jobs write derived data afterwards: a daily snapshot (4:05 PM ET) and a
summary (4:10 PM ET). Earnings refresh runs at 7:00 AM, the screener at 7:30 AM.

### Key invariants

- **Every decision is logged**, including holds and blocked trades. Zero rows for a cycle
  means the cycle never ran or crashed before the log step — a real diagnostic signal.
- **Virtual cash is derived from the trade ledger**, not read from the broker.
- **Blocking calls are wrapped** in `asyncio.to_thread()` so the event loop stays free.
- **Missing data must never become a number.** A price that cannot be fetched is not `0`.

## Services and responsibilities

| Concern | Where it lives | Notes |
|---|---|---|
| Auth | Supabase (Google OAuth, ES256) | Backend verifies via JWKS; no shared secret |
| Persistence | Supabase Postgres (pooler, 5432) | Direct connection does not work from Railway |
| Broker | `brokers/` — Alpaca primary, Schwab backup | Behind a `BrokerInterface` ABC |
| Decisions | `claude_brain.py` | Model id is a live operational risk — see decision log |
| Scheduling | `scheduler.py` (APScheduler) | Frequency derived from active portfolios |

## Feature module isolation

New features are self-contained packages under `backend/app/` with their own `models.py`,
logic, and `routes.py`. Shared infrastructure lives at the `app/` level instead.

The rule that keeps this honest: **do not import from one feature module to serve
another.** If the live executor needs strategies, it imports `app.strategies`, never
`app.backtest.strategies`.

## Deployment

| | Frontend | Backend |
|---|---|---|
| Root directory | `/frontend` | `/backend` |
| Notes | needs `HOSTNAME=0.0.0.0`; start command copies `.next/static` into standalone | — |

## TODO — thin areas

- TODO — where secrets and key rotation are handled (see `under-the-hood/runbook.md`).
- TODO — expected behaviour when Alpaca or Supabase is unreachable mid-cycle.
- TODO — data retention: how long trades, snapshots, and cached bars are kept.
