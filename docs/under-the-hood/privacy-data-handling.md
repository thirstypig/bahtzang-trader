---
id: DOC-019
type: privacy
status: draft
phase: null
owner: james
tags: [database, backend, deployment]
links: [DOC-007, DOC-020]
updated: 2026-07-22
---

# Privacy and data handling

## Scope — read this first

**This project has no customers and stores no third-party personal data.** It is a
single-operator experiment. That materially lowers the privacy stakes, and this document
should not pretend otherwise.

What it *does* handle is still sensitive, in two specific ways:

1. **Credentials with real power.** Broker keys, an LLM API key with billing attached,
   and database credentials. The Alpaca account is paper-only today, but the same key
   shape controls a live account.
2. **Financial records.** A complete trade and position history. No real money is at risk
   yet; that changes at Phase G.

**[unknown]** — whether access will ever extend beyond the operator. `ALLOWED_EMAIL`
already accepts a comma-separated list specifically so a second person can be added
without a code change. **The moment a second person logs in, this document needs
revisiting** — there is no per-user data scoping, so a second user sees everything.

## What is recorded

| Data | Where | Contains personal data? |
|---|---|---|
| Trades — every decision incl. holds and blocked | `trades` | No |
| Portfolio state and daily snapshots | `portfolios`, `plan_snapshots` | No |
| Strategy change history | `portfolio_strategy_audit` | No |
| Cached market data — bars, quotes, prices | `ohlcv_cache`, `ticker_prices`, `forex_bars` | No |
| Cached company profiles and earnings | `earnings_events`, profile cache | No |
| Screener runs and candidates | `screener_runs`, `screener_candidates` | No |
| Doc comments | `docs/_comments.json` | Author names only |
| Auth identity | Supabase | **Yes** — email, Google OAuth identity |
| Admin todos | `backend/data/todo-tasks.json` | Free text — whatever gets typed |

The only genuine personal data is the **authenticated email address**, held by Supabase.
The application stores an allow-list of permitted emails in an environment variable.

## Credentials

- Secrets live in environment variables — `backend/.env` locally, Railway in production.
- **`.env` is git-ignored and must stay that way.** Verify before every commit.
- Key *names* are documented in `backend/.env.example`; values never are.
- `system-status.md` reports only whether a key is present, never its value.

⚠ One key is currently set in `backend/.env` but absent from `.env.example` — see
`system-status.md`. Undocumented keys are how credentials get lost or duplicated.

## Retention — the honest gap

**There is no retention policy, and nothing is ever deleted.** Trades, snapshots, cached
bars, and screener runs accumulate indefinitely.

For a single-operator experiment that is a defensible choice — the history *is* the
research data, and deleting it would destroy the record. But it is a choice that was
never actually made, and it should be written down as one.

- TODO — decide and record a retention position for cached market data (`ohlcv_cache`,
  `forex_bars`), which grows without bound and has no research value once superseded.
- TODO — decide what happens to a deactivated portfolio's data. Test 4 and Test 5 are
  deliberately preserved as historical records; state that as policy.
- TODO — no deletion or export path exists for the authenticated user's identity.

## If this ever gains users

Not planned. Recorded so the gap is visible rather than discovered later:

- No per-user data scoping — every domain table lacks a `user_id`.
- No consent flow, no privacy policy, no data-export or deletion mechanism.
- Adding an email to `ALLOWED_EMAIL` grants **full access to everything**.
