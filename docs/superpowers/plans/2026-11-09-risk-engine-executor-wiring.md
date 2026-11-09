# Risk Engine → Executor Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every stock buy, for every portfolio, in every decision mode and run path, is sized by the risk engine and carries a broker-held GTC stop at Alpaca — and the virtual ledger stays truthful when that stop fires, is cancelled, or is in the way of a sell.

**Architecture:** `app/risk.py` gains one entry-sizing function (risk qty capped by cash and 20% of portfolio, earnings reduction, tick-rounded stop). `AlpacaBroker` gains get/cancel/standalone-stop calls and returns the OTO stop-leg id. A new `app/plans/stops.py` owns the stop lifecycle against the `trades` table (reconcile fired/cancelled stops, release stops before a sell, re-protect a partial-sell remainder). `_execute_plan_cycle` calls these at four touchpoints; nothing else in the pipeline changes.

**Tech Stack:** FastAPI backend, SQLAlchemy 2.0, alpaca-py `TradingClient`, pytest (SQLite in-memory).

**Spec:** `docs/product/prds/PRD-002-risk-defined-trading.md` (Phase 1) + `docs/product/trading-charter.md` §3 row 1 and §8 step 1.

## Global Constraints

- Stop = `2 × ATR(14)` below entry; risk per trade ≤ 1% of portfolio value. (PRD-002 §4.2–4.3, charter §3)
- Biggest single position ≤ 20% of portfolio value. (charter §3)
- Final qty = `min(risk_qty, floor(cash × 0.95 / entry), floor(0.20 × portfolio_value / entry))`, then earnings factor (0.5 at ≤1 day, 0.7 at 2 days), floored to whole shares. (PRD-002 §6 failure modes)
- No ATR, ATR ≤ 0, stop ≤ 0, or qty rounds to 0 → no trade; logged as a hold with the reason. Missing data never becomes a number.
- Stop leg is GTC (PR #44). OTO requires whole shares.
- Alpaca rejects sub-penny prices: stop ≥ $1 rounds DOWN to $0.01; stop < $1 rounds DOWN to $0.0001.
- Unconditional: no per-portfolio on/off flag (a flag that can be left off is the RISK-001 pattern). Constants live in `risk.py`; no new Portfolio columns.
- Crypto buys keep their current path (no broker stop possible). Charter step 5 removes crypto later.
- Safety limits in code only — no prompt changes in this plan.
- Every automatic stop event that changes holdings or leaves a position unprotected posts to Slack via `notifier`.

## Review Focus

1. A stop fires at 11:42 AM between cycles → next cycle must record the sell and credit cash before Claude sees positions; otherwise Claude "sells" shares that are gone and Alpaca sells someone else's (orphan MU/QQQ) shares. → Task 3 `test_fired_stop_recorded_before_decisions`.
2. Claude sells a position whose stop leg reserves the shares → Alpaca rejects the sell ("insufficient qty"). Must cancel this portfolio's legs first, and only this portfolio's. → Task 4 `test_sell_cancels_only_own_stop_first`.
3. Cancel races a fill (stop fired seconds before) → the sell must be blocked and the fill recorded, never a double sell. → Task 4 `test_cancel_race_records_fill_and_blocks_sell`.
4. Tight stop on a cheap, calm stock → risk qty exceeds cash / 20% → capped. → Task 1 `test_tight_stop_capped_by_cash` / `..._by_position_cap`.
5. Stop cancelled outside the system (Alpaca UI, corporate action) → position is silently naked. Must flag + Slack. → Task 3 `test_externally_cancelled_stop_flags_unprotected`.

---

### Task 1: Entry sizing + tick rounding in `risk.py`

**Files:**
- Modify: `backend/app/risk.py`
- Test: `backend/tests/test_risk.py`

**Interfaces:**
- Produces: `round_stop_price(price: float) -> float`; `size_entry(*, portfolio_value: float, cash: float, entry_price: float, atr: float | None, earnings_days: int | None = None) -> tuple[int, float]` returning `(qty, stop_price)`; constants `MAX_POSITION_PCT = 0.20`, `CASH_BUFFER = 0.95`. Raises `RiskError` on no ATR / non-positive stop. `qty == 0` means skip.

- [ ] **Step 1: Write failing tests** in `test_risk.py`, class `TestSizeEntry` + `TestRoundStopPrice`:
  - `test_risk_sized`: value 10_000, cash 10_000, entry 50, atr 2 → stop 46.0, qty 25 (100/4).
  - `test_tight_stop_capped_by_cash`: value 10_000, cash 1_000, entry 100, atr 0.25 → qty 9 (floor(950/100)).
  - `test_tight_stop_capped_by_position_cap`: value 10_000, cash 10_000, entry 100, atr 0.25 → qty 20 (20% = $2,000).
  - `test_earnings_tomorrow_halves`: risk case above with `earnings_days=1` → 12; `earnings_days=2` → 17.
  - `test_no_atr_raises`, `test_stop_at_or_below_zero_raises` (entry 1.0, atr 0.6).
  - `test_too_small_returns_zero`: value 100, cash 100, entry 500, atr 10 → qty 0.
  - `test_round_stop_price`: 46.239 → 46.23; 0.123456 → 0.1234; 11.57 → 11.57.
  - `test_stop_is_rounded`: entry 50, atr 1.3333 → stop 47.33.
- [ ] **Step 2:** `cd backend && venv/bin/pytest tests/test_risk.py -q` → new tests FAIL (ImportError).
- [ ] **Step 3: Implement.** `size_entry` reuses `compute_stop_price` + `compute_position_size` (risk_pct = `DEFAULT_RISK_PCT`), rounds the stop via `round_stop_price` *before* sizing, raises `RiskError` if rounded stop ≤ 0, applies the three caps, then the earnings factor, then `math.floor`. Use `math.floor(x * 100) / 100` style with a small epsilon guard (`+1e-9`) so 11.57 does not become 11.56.
- [ ] **Step 4:** same command → all PASS.
- [ ] **Step 5: Commit** `feat(risk): size_entry with cash/20% caps, earnings factor, tick-rounded stop`.

### Task 2: Broker stop-lifecycle calls + schema columns

**Files:**
- Modify: `backend/app/brokers/alpaca.py`, `backend/app/models.py` (Trade)
- Create: `backend/migrations/079_trade_stop_columns.sql`
- Test: `backend/tests/test_broker_bracket.py`

**Interfaces:**
- Produces on `AlpacaBroker`: `place_order(...)` result gains `"stop_order_id": str | None` (from `order.legs[0].id` when OTO); `async get_order(order_id: str) -> dict` → `{"status": str, "filled_qty": float, "filled_avg_price": float | None}` (status lower-case value, e.g. `"filled"`, `"held"`, `"canceled"`); `async cancel_order(order_id: str) -> str` → final status after polling `get_order` up to 5× at 0.5 s until not `pending_cancel`; `async place_stop_order(ticker: str, quantity: int, stop_price: float) -> dict` → `{"order_id", "status"}` (sell, `StopOrderRequest`, GTC).
- Produces on `Trade`: `stop_price: Numeric(14,4) | None`, `stop_order_id: String(64) | None`, `stop_state: String(16) | None` (`"open" | "filled" | "cancelled"`).
- Not added to `BrokerInterface` (Schwab is a backup with no stop support; ABC change would break it).

- [ ] **Step 1: Failing tests** (mock `_get_client`): `test_oto_result_includes_stop_leg_id`; `test_get_order_normalizes_status`; `test_cancel_order_waits_out_pending_cancel` (statuses pending_cancel → canceled); `test_cancel_order_reports_filled_when_raced` (returns `"filled"`); `test_place_stop_order_is_gtc_sell_stop`.
- [ ] **Step 2:** `venv/bin/pytest tests/test_broker_bracket.py -q` → FAIL.
- [ ] **Step 3: Implement** the four broker changes (all SDK calls via `asyncio.to_thread`; submits under `order_lock`). `cancel_order` swallows the SDK's "order is not cancelable" APIError and returns the order's current status instead. Add the three nullable `Trade` columns. Write `079_trade_stop_columns.sql` as three `ALTER TABLE trades ADD COLUMN IF NOT EXISTS ...` lines (house style: see 078).
- [ ] **Step 4:** full backend suite `venv/bin/pytest -q` → PASS.
- [ ] **Step 5: Commit** `feat(broker): stop-leg id, get/cancel order, standalone stop; trade stop columns`.

### Task 3: `stops.py` — reconcile fired / cancelled stops

**Files:**
- Create: `backend/app/plans/stops.py`
- Test: `backend/tests/plans/test_stops.py`

**Interfaces:**
- Consumes: Task 2 broker calls + Trade columns.
- Produces: `async reconcile_stops(db: Session, plan: Portfolio, broker) -> list[Trade]` — returns the sell rows it inserted.

- [ ] **Step 1: Failing tests** (fake broker object with `AsyncMock`s; seed with `make_plan` + executed buy rows carrying `stop_state="open"`):
  - `test_filled_stop_inserts_sell_and_credits_cash`: leg filled 10 @ 46.00 → new Trade(action sell, qty 10, price 46.00, executed, `alpaca_order_id` = leg id, reasoning starts `"Broker stop fired"`), buy row `stop_state="filled"`, `plan.virtual_cash` += 460, cash before/after set; Slack notifier called.
  - `test_open_stop_untouched` (status `held` / `new` / `accepted`) → no rows, state stays `open`.
  - `test_externally_cancelled_stop_flags_unprotected`: status `canceled` → `stop_state="cancelled"`, no sell row, warning + Slack mentions "UNPROTECTED".
  - `test_reconcile_is_idempotent`: run twice on a filled stop → one sell row.
  - `test_broker_error_leaves_state_open`: `get_order` raises → state `open`, no exception escapes.
- [ ] **Step 2:** `venv/bin/pytest tests/plans/test_stops.py -q` → FAIL.
- [ ] **Step 3: Implement.** Query `Trade` where `portfolio_id == plan.id` and `stop_state == "open"`. Commit per row (same atomic pattern as executor 063-fix). Use `notifier`'s existing send function (fire-and-forget).
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(stops): reconcile broker stops into the virtual ledger`.

### Task 4: `stops.py` — release before sell, re-protect remainder

**Files:**
- Modify: `backend/app/plans/stops.py`
- Test: `backend/tests/plans/test_stops.py`

**Interfaces:**
- Produces: `async release_stops(db, plan, ticker: str, broker) -> tuple[bool, float | None]` → `(ok_to_sell, highest_cancelled_stop_price)`; `async protect_remainder(db, plan, sell_trade: Trade, remaining_qty: float, stop_price: float, broker) -> None`.

- [ ] **Step 1: Failing tests:**
  - `test_sell_cancels_only_own_stop_first`: plan A and plan B each hold an open leg on AAPL → `release_stops(A, "AAPL")` cancels only A's leg id; returns `(True, A's stop)`; A's row `stop_state="cancelled"`.
  - `test_cancel_race_records_fill_and_blocks_sell`: `cancel_order` returns `"filled"` → returns `(False, None)`; a "Broker stop fired" sell row exists (delegates to the reconcile path for that row).
  - `test_no_open_stops_ok`: → `(True, None)`, no broker calls.
  - `test_protect_remainder_places_whole_share_stop`: remaining 7.6 @ stop 46.0 → `place_stop_order("AAPL", 7, 46.0)`; sell row gets `stop_order_id`, `stop_price`, `stop_state="open"`.
  - `test_protect_remainder_under_one_share_warns`: remaining 0.4 → no order, warning logged.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(stops): cancel own stop legs before sells; re-protect partial-sell remainder`.

### Task 5: Wire into `_execute_plan_cycle`

**Files:**
- Modify: `backend/app/plans/executor.py` (`_execute_plan_cycle`, lines ~295–635; new helper `_fetch_atr`)
- Modify: `backend/tests/conftest.py` (autouse ATR stub)
- Test: `backend/tests/plans/test_risk_wiring.py`; fix any existing executor tests whose buy quantities change

**Interfaces:**
- Consumes: `size_entry`, `RiskError` (Task 1); `reconcile_stops`, `release_stops`, `protect_remainder` (Tasks 3–4); `place_order(..., stop_price=)` result `stop_order_id` (Task 2).
- Produces: `async _fetch_atr(ticker: str) -> float | None` (wraps `get_indicators([ticker])[ticker]["atr14"]`, returns None on any error). Conftest autouse fixture patches it to return `2.0`; tests needing "no ATR" override.

Touchpoints, in cycle order:
1. First line of the cycle body: `await reconcile_stops(db, plan, broker)`, then `db.refresh(plan)` — before `compute_virtual_positions`.
2. Replace the Kelly block for **non-crypto** buys: `portfolio_value = remaining_cash + Σ virtual qty × (price_map price, else avg cost)`; `qty, stop = size_entry(...)`. `RiskError` or `qty == 0` → hold with reason `"Risk engine: <why>"`. Else set `decision["quantity"] = qty`, `decision["_stop_price"] = stop`, append `"[Risk engine: {qty} sh, stop ${stop:.2f} = 2×ATR ${atr:.2f}, max loss ≈ ${loss:.0f}]"`. Crypto buys keep the Kelly path unchanged.
3. Skip the fractional auto-resize block when `"_stop_price" in decision`.
4. Before a sell's `place_order`: `ok, prior_stop = await release_stops(...)`; `not ok` → `passed=False`, reason `"Sell skipped: broker stop already fired"`.
5. `place_order(..., stop_price=decision.pop("_stop_price", None))`; persist `stop_price`, `stop_order_id`, `stop_state="open"` on the buy Trade when a stop id came back.
6. After an executed partial sell with `prior_stop`: `protect_remainder(db, plan, plan_trade, plan_qty - qty, prior_stop, broker)`.

- [ ] **Step 1: Failing tests** in `test_risk_wiring.py` (pattern: `tests/plans/test_exit_only_cycle.py` — patch `claude_brain.get_trade_decision`, `executor.broker.*`):
  - `test_claude_qty_replaced_by_risk_size` (Claude asks 50, risk says 25 → order qty 25, `stop_price=46.0` passed to broker, Trade row `stop_state="open"`).
  - `test_rules_mode_buy_also_gets_stop` (`rules_decide`).
  - `test_no_atr_buy_becomes_hold` (no broker call, reason contains "Risk engine").
  - `test_fired_stop_recorded_before_decisions` (open leg reports filled → Claude's `positions` arg no longer contains the ticker; cash credited).
  - `test_sell_releases_stop_then_sells` (cancel called before `place_order`, call order asserted via a shared `Mock` parent).
  - `test_partial_sell_reprotects_remainder`.
  - `test_run_now_path_uses_risk_engine` (call via `run_plan_cycle`, same assertions as the first test).
- [ ] **Step 2:** FAIL. **Step 3:** implement touchpoints + conftest stub.
- [ ] **Step 4:** full suite `cd .. && npm test` → PASS; fix existing tests only where the buy qty legitimately changed (state the old/new number in the diff).
- [ ] **Step 5: Commit** `feat(executor): every stock buy risk-sized with a broker-held stop`.

### Task 6: Ship gate (human-in-the-loop)

- [ ] Update `docs/under-the-hood/feature-inventory.md` (stop-loss row → enforced at broker), CLAUDE.md pipeline block, changelog; `npm run docs:refresh`.
- [ ] Open PR. **Ask James before** applying `079_trade_stop_columns.sql` to the prod Supabase DB. Order matters: apply the migration **before** merging — the new ORM columns break every `trades` query on old schema; the additive nullable columns are harmless to the currently deployed code.
- [ ] After merge + deploy: confirm `\d trades` shows the columns and Railway logs show a clean cycle (0 active portfolios → reconcile is a no-op).
