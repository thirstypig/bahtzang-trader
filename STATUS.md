# STATUS — bahtzang-trader

**Last updated:** 2026-11-11

## One-line description
Personal AI trading experiment: Claude makes buy/sell/hold calls on an Alpaca paper account, with a Next.js dashboard and FastAPI backend. No real money yet.

## Scope / positioning
- Personal experiment, not a product.
- Paper trading under the trading charter (`docs/product/trading-charter.md`).
- Goal: pass the Phase G gate (≥12 weeks, ≥30 trades, beat SPY after costs) to earn a $200 live trial.
- Forex backtest tool kept separate from the trading pipeline.

## Stack & hosting
- Next.js 14 / React 18 / TypeScript / Tailwind frontend.
- FastAPI / SQLAlchemy / Anthropic SDK / APScheduler / alpaca-py backend.
- Supabase for auth and Postgres.
- Railway, two services (`backend/` and `frontend/` each have a `railway.toml`). DNS at Squarespace.
- GitHub Actions `test.yml`: pytest + Vitest.

## URLs
- https://www.bahtzang.com
- Backend: https://bahtzang-backend-production.up.railway.app

## Shipped (last 60 days)
- Standard local ports 3070/4070; PORTS.md retired (09-12).
- Feature inventory on the docs board (10-19).
- 2026-11-09, charter implementation:
  - Broker-held stops fixed: GTC instead of DAY.
  - Risk engine: every buy sized for ≤1% loss, with a broker-held stop that is reconciled each run.
  - Sells exempt from the cooldown and weekly cap.
  - Per-portfolio safety limits: holdings cap, daily buy cap, loss halts, -15% hard stop.
  - Cost tracking, plus a weekly report vs SPY after costs.
  - Stocks only; crypto turned off.
  - Conservative and Aggressive strategies ($10k paper each) launched.
  - Account-wide circuit breaker retired; stop fills dated correctly.

## In progress
- Conservative and Aggressive began trading 2026-11-10; the 12-week gate clock is running.
- Next step: watch the first cycles and the Friday reports.

## Open bugs / known issues
- About 16 positions (~$17.6k) from earlier tests have no owning portfolio. What to do with them is undecided.
- Several safety settings are saved but never read (feature inventory).
- Stale docs: the generated "Next 3 to-dos" and `roadmap.md` / `todos.md` (2026-07-22) still list risk-engine work that has shipped.
- `todos/102` (p3): bar-cache coverage-check polish.

## Next phases (in order)
From `docs/product/roadmap.md` (partly stale):
1. RM-001 Risk engine follow-ups: trailing-stop ratchet, heat/sector caps.
2. RM-002 Clean paper window, now Conservative/Aggressive.
3. RM-003 Paper-to-live transition ($200).
4. RM-004 Retroactive PRDs for features already built.
5. RM-005 Trend-following strategy (Phase H).
6. RM-006 Per-user data isolation (parked).

## Decisions changed recently
- Phase G gate changed from "zero losing weeks" to "beat SPY after costs" (10-19).
- Test 5 stopped at -9.3% vs SPY +3.0%; experiment reset (10-19).
- Charter simplified to two Claude strategies (11-09).
- Crypto turned off; Pools A/B/C dropped (OTC can't be priced on the current data plan).
- Account-wide circuit breaker replaced by per-portfolio limits (11-09).
- The risk engine, not Claude, now sets trade quantity.
