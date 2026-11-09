# Charter §3 Safety Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce in code, per portfolio and on every run path (scheduler, /run, Run Now), the charter §3 limits not yet live: ≤8 holdings, ≤2 new buys/day, -3% day and -6% week buy halts, -15% hard stop that switches the portfolio off — every halt posted to Slack.

**Architecture:** One new module `backend/app/plans/limits.py` (feature isolation: per-portfolio, reads only `plans` + `models` tables). The executor gets exactly two touchpoints: a cycle-start gate (halts + hard stop) and a per-buy gate (holdings + daily buys). The account-wide `circuit_breaker.py` is left untouched.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest (SQLite in-memory).

**Spec:** `docs/product/trading-charter.md` §3 (rows: max holdings, new buys per day, daily loss halt, weekly loss halt, hard stop, every run path; "Any automatic halt posts to Slack").

## Global Constraints

- `MAX_HOLDINGS = 8`, `MAX_NEW_BUYS_PER_DAY = 2`, `DAILY_HALT_PCT = 0.03`, `WEEKLY_HALT_PCT = 0.06`, `HARD_STOP_PCT = 0.15` — constants in `limits.py`, no Portfolio columns (same "no off switch" ruling as the risk engine).
- Limits block **buys only**. Sells always pass (charter §3, shipped in #47).
- "Day" and "week" are US/Eastern calendar day and Monday-start week (`zoneinfo.ZoneInfo("America/New_York")`).
- Portfolio value now = `virtual_cash + Σ qty × (live price, else avg cost)`. Missing data never inflates value silently: a missing price falls back to avg cost and is logged.
- Daily reference = the latest `PlanSnapshot.total_value` dated **before today**; weekly reference = latest snapshot dated **before this Monday**; either missing → `plan.budget`.
- Hard stop reference = `plan.budget` (starting capital).
- Every halt and the hard stop call `notifier.notify_risk_event`.

## Review Focus

1. Brand-new portfolio (no snapshots) → references fall back to budget; must not halt or crash. → Task 1 `test_no_snapshots_uses_budget`.
2. Adding to an existing holding when already at 8 → allowed (it's not a new holding). → Task 1 `test_add_to_existing_allowed_at_eight`.
3. Two buys in the same cycle → the second counts the first (DB count after per-trade commit). → Task 2 `test_third_buy_same_day_blocked`.
4. Hard stop on Run Now → portfolio switched off, no orders, Slack. → Task 2 `test_hard_stop_switches_off_and_places_nothing`.
5. Halted portfolio still sells. → Task 2 `test_daily_halt_blocks_buy_not_sell`.

---

### Task 1: `plans/limits.py`

**Files:** Create `backend/app/plans/limits.py`; Test `backend/tests/plans/test_limits.py`

**Interfaces — Produces:**
- `portfolio_value(cash: float, positions: dict[str, float], price_map: dict, avg_costs: dict) -> float`
- `@dataclass(frozen=True) class CycleLimits: hard_stop: bool; buy_halt: str | None` (reason text or None)
- `evaluate_cycle_limits(db: Session, plan: Portfolio, current_value: float, today: date) -> CycleLimits` — hard stop if `current_value <= budget × (1 - HARD_STOP_PCT)`; else buy_halt if day change ≤ -3% (reason starts `"Daily loss halt"`) or week change ≤ -6% (`"Weekly loss halt"`).
- `buy_block_reason(db: Session, plan: Portfolio, ticker: str, positions: dict[str, float], limits: CycleLimits, now: datetime) -> str | None` — order: halt → `"Max holdings: 8 held"` (only if ticker not already held) → `"Max new buys: 2 today"` (executed buys since ET midnight).
- `async switch_off(db: Session, plan: Portfolio, current_value: float) -> None` — `is_active=False`, commit, Slack text contains `"HARD STOP"`.

- [ ] **Step 1: Failing tests** (`make_plan` budget 10_000; snapshots via `PlanSnapshot` rows):
  - `test_portfolio_value_uses_price_then_avg_cost`: cash 1000, {A:10, B:5}, price A=20, B missing, avg B=30 → 1350.
  - `test_no_snapshots_uses_budget`: value 9_800 → no halt, no hard stop.
  - `test_daily_halt_vs_yesterday_snapshot`: yesterday snapshot 10_000, value 9_690 → halt "Daily loss halt"; 9_710 → none.
  - `test_weekly_halt_vs_last_week_snapshot`: snapshot dated last Friday 10_000 (and a yesterday snapshot 9_400 so day is flat), value 9_390 → "Weekly loss halt".
  - `test_hard_stop_at_15pct`: value 8_500 → hard_stop True; 8_510 → False.
  - `test_halt_blocks_buy`, `test_ninth_new_holding_blocked`, `test_add_to_existing_allowed_at_eight`, `test_two_buys_today_blocks_third` (two executed buys timestamped today ET; one yesterday doesn't count).
  - `test_switch_off_deactivates_and_alerts` (patch `app.plans.limits.notifier.notify_risk_event`).
- [ ] **Step 2:** `cd backend && venv/bin/pytest tests/plans/test_limits.py -q` → FAIL (module missing).
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(limits): per-portfolio holdings, daily-buy, loss-halt and hard-stop checks`.

### Task 2: Two executor touchpoints + prompt alignment

**Files:** Modify `backend/app/plans/executor.py`; Test `backend/tests/plans/test_limits_wiring.py`

**Interfaces — Consumes:** all of Task 1.

Touchpoints:
1. In `_execute_plan_cycle`, right after `avg_costs` is computed: `value = portfolio_value(...)`; `limits = evaluate_cycle_limits(db, plan, value, today_et)`; if `limits.hard_stop`: `await switch_off(...)`; `return []` (no Claude call, no orders; broker stops stay in place).
2. In the decision loop, for `action == "buy"` **before** risk sizing (saves an ATR fetch): `reason = buy_block_reason(...)` → hold with that reason; if `limits.buy_halt` blocked a buy, send one Slack per cycle (`"<name>: buys halted — <reason>"`).
- `_apply_risk_sizing` uses `portfolio_value()` instead of its inline sum (no behavior change).
- `_plan_to_guardrails_config`: `config["max_positions"] = MAX_HOLDINGS` so the prompt's slot count matches what code enforces.

- [ ] **Step 1: Failing tests** (pattern: `tests/plans/test_risk_wiring.py`):
  - `test_hard_stop_switches_off_and_places_nothing` (plan cash 8_000, no positions, budget 10_000 → `is_active` False, Claude not called, broker not called).
  - `test_daily_halt_blocks_buy_not_sell` (yesterday snapshot 10_000, value 9_600; decisions = buy MSFT + sell AAPL held → buy is hold "Daily loss halt", sell executes).
  - `test_third_buy_same_day_blocked` (two executed buys earlier today; Claude buys a third → hold "Max new buys").
  - `test_ninth_holding_blocked_in_cycle`.
  - `test_prompt_max_positions_is_eight` (assert `guardrails_config["max_positions"] == 8` passed to Claude).
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** full suite `cd backend && venv/bin/pytest -q` → PASS (fix existing tests only where a limit legitimately now applies; say which in the commit).
- [ ] **Step 5: Commit** `feat(executor): enforce charter §3 limits at cycle start and per buy`.

### Task 3: Ship

- [ ] Feature inventory rows (max positions, daily order limit, circuit breaker note), CLAUDE.md status/pipeline, changelog 0.35.0; `npm run docs:refresh`; PR. No migration needed.

## Rulings carried into this plan (for James)

- **Hard stop ends the portfolio's run outright** — no Claude call, no sells. Broker-held stops remain in force; unwinding is manual (matches "Rollback = kill switch + manual unwind").
- **Account-wide circuit breaker left as is.** It's outside §3, measures the whole account (incl. orphan positions), and its loss-streak rule is a proxy. Retiring or fixing it is a separate decision.
- **Saved-but-unread settings** (`min_confidence`, `kelly_fraction`, `circuit_breaker_*`, `respect_wash_sale`) are **not** in this plan — they aren't charter §3 limits. Separate cleanup.
- **Prompt's "orders today / limit" line still shows the preset (sells + buys)**; only `max_positions` is aligned. The code blocks the 3rd buy regardless.
