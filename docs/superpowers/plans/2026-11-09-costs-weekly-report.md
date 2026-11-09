# Cost Tracking + Weekly Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "beat SPY after all costs" measurable: record spread, regulatory fees and Claude API cost per portfolio; apply the same cost model in the backtester; produce a saved weekly report (per portfolio + account; week and since start) with a Claude-drafted learning note, shown on a /reports page.

**Architecture:** `app/costs.py` (shared infra: constants + pure functions, used by live and backtest). Live recording hooks in the executor/stops/claude_brain write `trades.spread_cost`, `trades.fee_cost` and new `api_usage` rows. New feature package `app/reports/` (models, engine, routes) reads the ledger; scheduler runs it Fridays 4:20 PM ET. Frontend `/reports` page renders saved reports.

**Tech Stack:** FastAPI, SQLAlchemy, alpaca-py data client (`StockLatestQuoteRequest`), Anthropic SDK (`claude-sonnet-4-6`, the model the bot already uses), Next.js 14 + Vitest.

**Spec:** `docs/product/trading-charter.md` §1 (costs = spread, fees, API bill, estimated tax), §4, §5, §7. James's choices (2026-11-09): report = saved page only (no Slack); backtester cost model in this step; estimate sell fees; Claude drafts the learning note.

## Global Constraints

- Fee constants (dated, sourced, in `costs.py`): SEC Section 31 **$20.60 per $1M of sale proceeds** (effective 2026-04-04); FINRA TAF **$0.000195 per share sold, max $9.79 per trade** (2026). Sells only.
- Spread cost per executed trade = `qty × (ask − bid) / 2` from Alpaca's latest quote at order time. Missing/invalid quote (bid ≤ 0, ask ≤ bid) → `spread_cost = NULL` and the report counts it as "unpriced", never as 0.
- Backtester has no quotes: assumed half-spread `BACKTEST_HALF_SPREAD_BPS = 5` (0.05%) per fill, labelled as an assumption in results.
- API cost: Sonnet 4.6 **$3 / 1M input, $15 / 1M output, cache write 1.25× input, cache read 0.1× input**; fields `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` (None → 0).
- Estimated tax: **24%** of net realized short-term gains in the period, floored at 0 (losses offset gains within the period; no carry-forward — stated in the report).
- Realized P&L per sell = average-cost method replayed over the portfolio's executed trades (same method as `compute_virtual_cost_basis`).
- Week = Monday–Friday ET; week start value = latest snapshot before Monday (else budget); end value = Friday's snapshot (else value computed now).
- No Slack for the report. Feature isolation: `reports → plans` is a read-only consumer; add it to the allow-list in `tests/test_feature_isolation.py` with that reason.

## Review Focus

1. A trade with no quote → spread unknown, not zero; report shows the unpriced count. → Task 2 `test_missing_quote_records_null_spread`, Task 4 `test_unpriced_spread_reported`.
2. A sell at a loss after a gain in the same week → tax on the net, floored at 0. → Task 1 `test_tax_on_net_gain_floored`.
3. Claude call fails or returns no usage → cycle still runs, no crash, no row. → Task 2 `test_missing_usage_records_nothing`.
4. Portfolio with no trades/snapshots in the week → report row with zeros, not a crash. → Task 4 `test_empty_week_report`.
5. Broker stop fill → fee recorded on the sell (spread NULL). → Task 2 `test_stop_fill_records_fee`.

---

### Task 1: `app/costs.py`

**Files:** Create `backend/app/costs.py`; Test `backend/tests/test_costs.py`

**Produces:** `sell_fees(qty: float, price: float) -> float`; `half_spread_cost(qty: float, bid: float | None, ask: float | None) -> float | None`; `api_cost(usage) -> float` (any object with the four usage attrs); `@dataclass RealizedSell(trade_id, ticker, qty, proceeds, cost_basis, gain)`; `realized_sells(trades: list[Trade]) -> list[RealizedSell]` (input sorted by timestamp, id; buys update avg cost; sells realize); `estimated_tax(gains: list[float]) -> float`; constants above.

- [ ] Tests: `test_sell_fees` (100 sh @ $50 → SEC 0.103 + TAF 0.0195 = 0.1225); `test_taf_capped` (100,000 sh @ $1 → TAF 9.79); `test_half_spread_cost` (10 sh, 49.98/50.02 → 0.20); `test_bad_quote_is_none` (bid 0; ask<bid); `test_api_cost` (1000 in, 500 out, 2000 cache read, 0 write → 0.003+0.0075+0.0006 = 0.0111); `test_api_cost_none_fields`; `test_realized_sells_avg_cost` (buy 10@10, buy 10@20, sell 5@30 → gain 75); `test_tax_on_net_gain_floored` ([100, -40] → 14.4; [-50] → 0).
- [ ] RED → implement → GREEN → commit `feat(costs): shared cost model — fees, spread, API, realized P&L, tax`.

### Task 2: Record live costs

**Files:** Modify `backend/app/models.py` (Trade cols + `ApiUsage` model), `backend/app/brokers/alpaca.py`, `backend/app/claude_brain.py`, `backend/app/plans/executor.py`, `backend/app/plans/stops.py`, `backend/app/plans/limits.py`; Create `backend/migrations/080_costs.sql`; Test `backend/tests/plans/test_cost_recording.py`

**Produces:**
- `Trade.spread_cost: Numeric(14,4) | None`, `Trade.fee_cost: Numeric(14,4) | None`.
- `ApiUsage` table `api_usage`: id, timestamp (UTC), portfolio_id (nullable FK, SET NULL), purpose (`"decision" | "oversight" | "report_note"`), model, input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, cost Numeric(12,6).
- `AlpacaBroker.get_bid_ask(ticker: str) -> tuple[float | None, float | None]` (latest quote via `StockHistoricalDataClient.get_stock_latest_quote`; any error → (None, None)).
- `claude_brain.get_trade_decision(..., usage_sink: list | None = None)` and `review_trade_decision(..., usage_sink=None)`: append `message.usage` when present.
- Executor: pass a per-cycle `usage_sink`, then write one `ApiUsage` row per usage (purpose by mode). Before each executed order fetch bid/ask → `spread_cost`; sells get `fee_cost = sell_fees(...)`.
- `stops._record_fill`: `fee_cost = sell_fees(qty, price)`, spread NULL.
- `limits.switch_off`: also writes a hold Trade row whose reasoning starts `"HARD STOP"` (audit trail; fixes the deferred "no row" minor).
- `080_costs.sql`: `ALTER TABLE trades ADD COLUMN IF NOT EXISTS spread_cost NUMERIC(14,4) NULL; ... fee_cost ...;` `CREATE TABLE IF NOT EXISTS api_usage (...)`; backtest columns from Task 3.

- [ ] Tests: `test_buy_records_spread`, `test_sell_records_spread_and_fee`, `test_missing_quote_records_null_spread`, `test_stop_fill_records_fee`, `test_decision_usage_recorded_per_portfolio`, `test_missing_usage_records_nothing`, `test_hard_stop_writes_audit_row`.
- [ ] RED → implement → full suite GREEN → commit `feat(costs): record spread, sell fees and Claude API cost per portfolio`.

### Task 3: Backtester cost model

**Files:** Modify `backend/app/backtest/engine.py`, `backend/app/backtest/models.py`; Test `backend/tests/test_backtest_costs.py`

**Produces:** `BacktestResult.total_costs: Float | None`, `return_after_costs_pct: Float | None` (in 080). Engine: each buy pays `price × qty × bps`, each sell pays the same spread + `sell_fees`; at the end, `estimated_tax` on the run's realized sell gains; `return_after_costs_pct = (final_equity − total_costs_not_already_in_equity − tax) / initial − 1`. Spread + fees reduce cash at fill time (so they're inside equity); tax is applied at the end. `trades_log` entries gain `spread_cost`/`fee_cost`. `to_summary()` exposes both new fields and `"cost_assumptions": {"half_spread_bps": 5, ...}`.

- [ ] Tests: `test_round_trip_pays_spread_and_fees` (deterministic bars, one buy/sell → exact cash), `test_after_cost_return_below_gross`, `test_tax_only_on_net_gains`.
- [ ] RED → implement → GREEN → commit `feat(backtest): same cost model as live — spread assumption, sell fees, est. tax`.

### Task 4: `app/reports/` weekly report

**Files:** Create `backend/app/reports/{__init__,models,engine,routes}.py`; Modify `backend/app/models.py` (import), `backend/app/main.py` (router), `backend/app/scheduler.py` (Fri 16:20 ET job), `backend/tests/test_feature_isolation.py` (allow `("reports","plans")`); Test `backend/tests/reports/test_weekly_report.py`

**Produces:**
- `WeeklyReport` table `weekly_reports`: id, week_ending (date), created_at, payload (JSON), note (Text), note_model (str|None). Unique on week_ending (re-run replaces).
- `build_weekly_report(db, week_ending: date, spy_closes: dict[date, float]) -> dict` (pure over DB + given SPY closes) returning `{"week_ending", "portfolios": [row...], "account": row, "assumptions": {...}}` where each row has: name, id, start_value, end_value, return_pct, after_cost_return_pct, spy_return_pct, beat_spy (bool after costs), since_start {return_pct, after_cost_return_pct, spy_return_pct}, trades, wins, losses, win_rate, avg_win, avg_loss, costs {spread, spread_unpriced_trades, fees, api, est_tax, total}, limit_events [{type, count}] (types from trade reasoning prefixes: "Daily loss halt", "Weekly loss halt", "Max holdings", "Max new buys", "Risk engine", "Broker stop fired", "HARD STOP", "UNPROTECTED" not in trades → skip).
- `async run_weekly_report(db, week_ending=None) -> WeeklyReport`: fetches SPY closes via `app.bars`, builds payload, asks Claude (`claude-sonnet-4-6`, max_tokens 1200) for a ≤150-word "what we learned / what we'd change" draft explicitly framed as a draft for James's review and limited to at most one rule change per portfolio (charter §6); records `ApiUsage(purpose="report_note")`; note failure → saved with `note=None`.
- Routes: `GET /reports` (list: id, week_ending, headline per portfolio), `GET /reports/{id}`, `POST /reports/run` (auth, rate-limited 2/min).
- Scheduler: Friday 16:20 America/New_York.

- [ ] Tests: `test_return_vs_spy_before_and_after_costs`, `test_empty_week_report`, `test_unpriced_spread_reported`, `test_limit_events_counted`, `test_since_start_uses_budget`, `test_rerun_replaces_week`, `test_note_failure_still_saves` (Claude patched to raise), `test_routes_list_and_detail`.
- [ ] RED → implement → full suite GREEN → commit `feat(reports): weekly report vs SPY after costs with Claude-drafted note`.

### Task 5: `/reports` page

**Files:** Create `frontend/src/app/reports/page.tsx` (+ detail rendering in same page via selected id), `frontend/src/app/reports/__tests__/page.test.tsx`; Modify `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/components/TopNav.tsx` (Trading group: "Weekly reports").

- [ ] Page: auth-gated `useApiQuery`; list of weeks; selected week shows a table per portfolio (return, after costs, SPY, beat?, costs breakdown, limit events) + the note under the heading "Draft note (Claude) — review before acting". Semantic tokens + `.bz-glass` only. Empty state: "No reports yet — the first one is written Friday after the close."
- [ ] Tests (Vitest): renders list + detail from mocked API; empty state.
- [ ] RED → implement → `npx vitest run` + `npx tsc --noEmit` GREEN → commit `feat(frontend): weekly reports page`.

### Task 6: Ship

- [ ] Feature inventory, CLAUDE.md, changelog 0.36.0, `npm run docs:refresh`, PR. **James applies `080_costs.sql` to prod before merge** (new columns on `trades`/`backtest_results`; new tables are also created by `create_all`, but the SQL file creates them too for parity).
