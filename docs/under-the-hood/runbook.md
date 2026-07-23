---
id: DOC-020
type: runbook
status: active
phase: null
owner: james
tags: [deployment, backend, database]
links: [DOC-007, DOC-017, DOC-019]
updated: 2026-07-22
---

# Runbook

How to operate this system when something needs checking or has gone wrong.

> Procedures below were verified on 2026-07-22 while diagnosing a live incident. Anything
> unverified is marked TODO rather than guessed — a runbook you cannot trust is worse
> than no runbook, because you follow it under pressure.

## Is it actually running?

The most important question, and the least obvious to answer. **A healthy-looking system
can be completely dead** — see RISK-003.

```bash
# Process alive? Both responses below mean UP.
curl -s -o /dev/null -w "%{http_code}" https://bahtzang-backend-production.up.railway.app/
#   404          → up (no root route)
#   timeout      → DOWN

curl -s https://bahtzang-backend-production.up.railway.app/bot/status
#   {"detail":"Not authenticated"}  → up (endpoint exists, auth required)
```

**Liveness is not health.** The June outage had a live process, a running scheduler, and
correctly configured keys — and made zero trades for 13 days. The only reliable check is
whether rows are landing in `trades`.

## Did the bot trade today?

Every cycle writes a row **even for holds and blocked trades**. So:

> **Zero rows for a cycle means the cycle never ran, or crashed before the logging step.**
> It does not mean the market was quiet.

```bash
DBURL=$(grep -E '^DATABASE_URL=' backend/.env | cut -d= -f2- | tr -d '"')
export PGCONNECT_TIMEOUT=15
export PATH="/opt/homebrew/opt/libpq/bin:$PATH"     # psql lives here

psql "$DBURL" -P pager=off -c \
  "SELECT timestamp, ticker, action, quantity, price, executed
     FROM trades WHERE portfolio_id=6 ORDER BY timestamp DESC LIMIT 10;"
```

`backend/.env`'s `DATABASE_URL` points at the **production** Supabase pooler. There is no
separate local database. Read-only `SELECT`s are safe; anything else is production.

### Column gotchas

`trades` does **not** have the columns you expect. There is no `status` and no
`created_at`. Use `timestamp` and `executed`.

Real columns: `id, timestamp, ticker, action, quantity, price, claude_reasoning,
confidence, guardrail_passed, guardrail_block_reason, executed, portfolio_id,
alpaca_order_id, virtual_cash_before, virtual_cash_after, rules_recommendation`

### Key tables

| Table | Notes |
|---|---|
| `portfolios` | Test 5 = **id 6** (active). Test 4 = id 5 (deactivated, preserved). |
| `trades` | One row per decision, always |
| `plan_snapshots` | Daily valuation. One row per portfolio per day |
| `screener_runs` | A run stuck at `status='running'` means it crashed mid-flight |

## Reading production logs

```bash
env -u RAILWAY_API_TOKEN railway whoami      # confirm login
env -u RAILWAY_API_TOKEN railway logs -d     # deploy + runtime logs
env -u RAILWAY_API_TOKEN railway logs -b     # build logs
```

⚠ **A stale `RAILWAY_API_TOKEN` in the shell environment breaks both the CLI and the
Railway MCP** (`whoami` returns Unauthorized). Unsetting it per-command falls back to the
valid browser-login session underneath. This is not obvious and costs time every time.

`railway logs` streams — cap it or it will hang your terminal. Run it in the background,
wait ~12s, then kill it.

Project is linked as `bahtzang-trader / production / bahtzang-backend`.

## Deploying

Both services deploy from the same GitHub repo on push to `main`.

| | Frontend | Backend |
|---|---|---|
| Root directory | `/frontend` | `/backend` |
| Gotchas | needs `HOSTNAME=0.0.0.0`; start command copies `.next/static` into the standalone dir | — |

- The pre-commit hook runs tsc + eslint + pytest + vitest. It is the real gate.
- Run `npm run docs:refresh` before pushing so generated docs do not drift.
- **Deploys can fail silently.** See `docs/solutions/deployment-issues/` for two recorded
  cases — a pandas-ta build failure and eslint rot on the frontend.

## Failure playbooks

### The bot stopped trading

The pattern to recognise, in order:

1. Check `trades` for recent rows. Zero rows over multiple days → the cycle is dying.
2. Read `railway logs -d` and look for the cycle error. The June case showed
   `Plan 6 cycle failed: ... 404 not_found_error 'model: ...'` followed by
   "0 portfolios processed".
3. Model ids get **retired by the vendor without warning**. That is a live, recurring
   operational risk, not a one-off. Current id lives in `claude_brain.py`.

### A market data source is failing

Alpha Vantage returns **HTTP 200 with a rate-limit notice** when throttled, so
`raise_for_status()` passes and the price silently becomes `0`. Symptoms: implausible
valuations, positions appearing worthless.

Snapshots now price from Alpaca instead and refuse to write when a position cannot be
priced. Other AV call sites have not been audited (RISK-002).

### A screener run is stuck

A run left at `status='running'` crashed mid-flight. The error handler was fixed so
failures now record properly, but pre-fix runs remain stranded and can be ignored.

## Key rotation

- TODO — no rotation procedure has been written or tested.
- Keys live in Railway environment variables for production, `backend/.env` locally.
- Rotating a key means updating **both**, then redeploying.
- TODO — confirm whether Railway redeploys automatically on an env var change.

## Local development gotchas

- **`python` on PATH is not the project interpreter.** Use `backend/venv/bin/python`.
- `pandas_ta`'s `.ta` accessor is broken under the local Python build; production differs.
- Ports: frontend **3070**, backend **4070**.
