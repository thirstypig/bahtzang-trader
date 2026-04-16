# Investment Plans (Pie-Style Portfolio Slices)

**Date:** 2026-04-15
**Status:** Draft — Deepened
**Author:** Jimmy + Claude

## Enhancement Summary

**Deepened on:** 2026-04-15
**Research agents used:** 6 (virtual portfolio tracking, multi-strategy scheduling, feature module isolation, pie chart UI, security sentinel, performance oracle)

### Key Improvements from Research
1. **Security**: Two critical gaps identified — virtual cash overallocation and cross-plan position theft — with concrete guardrails added
2. **Performance**: Claude calls should run in parallel (2-5s total vs 6-15s sequential); market data fetched once and shared
3. **Alpaca**: Confirmed fractional shares supported via `notional` orders — critical for $50-100 plan budgets
4. **Scheduling**: One job per plan with jitter + global execution lock — isolates failures, prevents races
5. **Cost**: At 1x frequency with 3 plans, Claude API cost is ~$0.30/month; at 5x it's ~$1.50/month

### Critical Findings
- Alpaca has NO native sub-account support — virtual ledger must be built at app layer
- The existing `_cycle_lock` must guard Alpaca order execution only, NOT Claude calls, or parallelism is lost
- Every budget mutation (create/update) must atomically validate `SUM(budgets) <= account_equity`
- Per-plan guardrails must scope queries to `plan_id` — not the global `trades` table

---

## Problem Statement

The trading bot currently treats the entire Alpaca account as a single pool with one goal, one risk profile, and one strategy. This limits diversification and makes it impossible to run different strategies simultaneously (e.g., aggressive growth on $100 + steady income on $100).

Users want to split their budget into multiple independent "plans" (like M1 Finance pies or Wealthfront portfolios), each with its own:
- Budget allocation
- Trading goal and risk profile
- Independent trade history and P&L tracking
- Separate Claude decision context

## Goals

1. Allow users to create multiple investment plans with independent configurations
2. Each plan operates as an isolated trading unit with its own budget, goal, and history
3. Plans share a single Alpaca brokerage account but track virtual allocations in the database
4. Dashboard shows per-plan performance alongside total portfolio view
5. Support for small accounts ($200 total split across 2-3 plans)

## Proposed Solution

### Architecture: Feature Module Isolation

Follow the established pattern from `backtest/` and `earnings/` modules:

```
backend/app/plans/
├── __init__.py          # Module docstring only
├── models.py            # Plan, PlanTrade, PlanSnapshot tables
├── routes.py            # CRUD + per-plan trading cycles (APIRouter with prefix="/plans")
├── executor.py          # Per-plan trade execution with virtual cash tracking
└── allocation.py        # Budget allocation, reconciliation, virtual position calculation

frontend/src/app/plans/
├── page.tsx             # Plans overview — donut chart of allocations + plan cards
├── [id]/
│   └── page.tsx         # Individual plan detail — trades, P&L, settings
└── new/
    └── page.tsx         # Create new plan wizard
```

### Research Insights: Module Registration

From the existing codebase pattern (backtest, earnings):

1. `plans/__init__.py` — module docstring only
2. `plans/models.py` — SQLAlchemy classes inheriting from `Base`
3. `plans/routes.py` — `router = APIRouter(prefix="/plans", tags=["plans"])`, all endpoints use `Depends(require_auth)` and `Depends(get_db)`
4. Root `models.py` — add `from app.plans.models import Plan, PlanTrade, PlanSnapshot  # noqa: F401`
5. `main.py` — add `from app.plans.routes import router as plans_router` and `app.include_router(plans_router)`
6. No inter-feature imports (plans module must not import from backtest or earnings)

### Data Model

```python
class Plan(Base):
    __tablename__ = "plans"
    id: int                    # Primary key
    name: str                  # "Growth Slice", "Income Slice"
    budget: float              # Allocated dollars (e.g., $100)
    virtual_cash: float        # Current available cash in this plan
    trading_goal: str          # One of the 6 goals
    risk_profile: str          # conservative/moderate/aggressive
    trading_frequency: str     # 1x/3x/5x
    target_amount: float|None  # Timeline goal target
    target_date: str|None      # Timeline goal date
    is_active: bool            # Pause/resume
    created_at: datetime
    updated_at: datetime

class PlanTrade(Base):
    __tablename__ = "plan_trades"
    id: int
    plan_id: int               # FK to plans
    timestamp: datetime
    ticker: str
    action: str                # buy/sell/hold
    quantity: float            # Float for fractional shares
    price: float|None
    claude_reasoning: str|None
    confidence: float|None
    guardrail_passed: bool
    guardrail_block_reason: str|None
    executed: bool
    virtual_cash_before: float
    virtual_cash_after: float

    __table_args__ = (
        Index("ix_plan_trades_plan_timestamp", "plan_id", timestamp.desc()),
        Index("ix_plan_trades_plan_ticker", "plan_id", "ticker", "timestamp"),
        Index("ix_plan_trades_plan_executed", "plan_id", "executed", "timestamp"),
        Index("ix_plan_trades_timestamp_desc", timestamp.desc()),
    )

class PlanSnapshot(Base):
    __tablename__ = "plan_snapshots"
    id: int
    plan_id: int               # FK to plans
    date: date
    budget: float
    virtual_cash: float
    invested_value: float
    total_value: float
    pnl: float
    pnl_pct: float
```

### Research Insights: Data Model

- **`quantity` is `float`, not `int`** — Alpaca supports fractional shares via `notional` orders. For a $50 plan buying AAPL at $200, that's 0.25 shares. Use `notional` param in Alpaca API: `{"symbol": "AAPL", "notional": "50", "side": "buy", "type": "market", "time_in_force": "day"}`
- **`virtual_cash` stored on Plan model** — avoids recomputing from full trade history on every cycle. Updated atomically with each trade execution.
- **4 indexes on PlanTrade** — covers the primary query patterns: plan detail page, virtual position calculation, P&L filtering, and global trade feed.
- **~19,500 rows/year** max at 3 plans × 5x frequency × 5 decisions. Trivial for PostgreSQL, no partitioning needed.

### Virtual Cash Tracking

Since all plans share one Alpaca account, we track allocations virtually:

- Each plan has a `budget` (initial allocation) and `virtual_cash` (current available cash)
- When Plan A buys $20 of NVDA, Plan A's `virtual_cash` decreases by $20
- When Plan A sells, `virtual_cash` increases by the proceeds
- The sum of all plan budgets must not exceed the Alpaca account's total value
- Real Alpaca positions are tagged by which plan owns them (tracked in PlanTrade)

### Research Insights: Virtual Cash (from robo-advisor patterns)

**M1 Finance approach**: Allocations are tracked as target percentages, and new deposits go to the most underweight slice first. For our fixed-budget model:
- `plan.virtual_cash` is the source of truth for available cash per plan
- `plan.budget` is the total allocation (cash + invested)
- Virtual positions are computed from `SUM(quantity) GROUP BY ticker WHERE plan_id = X AND executed = true` (buys positive, sells negative)
- **Daily reconciliation**: Compare `SUM(virtual_position_qty × current_price) + virtual_cash` across all plans against real Alpaca equity. Log discrepancies but don't auto-correct — flag for human review.

### Security Guardrails (CRITICAL)

**1. Budget Overallocation Prevention (P1)**
```python
# On every plan create/update:
total_budgets = db.query(func.sum(Plan.budget)).scalar() or 0
account_equity = await broker.get_account_balance()
if total_budgets + new_budget > account_equity["total_value"]:
    raise HTTPException(400, "Total plan budgets exceed account value")
```

**2. Cross-Plan Position Theft Prevention (P1)**
```python
# Before every sell execution:
plan_qty = compute_virtual_position(db, plan_id, ticker)  # net qty from PlanTrade history
if sell_qty > plan_qty:
    block_reason = f"Plan only owns {plan_qty} shares of {ticker}, cannot sell {sell_qty}"
    # Block the trade
```

**3. Pre-Execution Equity Check (P1)**
```python
# Before every buy execution:
total_virtual = sum(plan.virtual_cash + plan.invested_value for plan in all_plans)
if total_virtual > real_account_equity * 1.01:  # 1% tolerance
    block_reason = "Virtual allocations exceed real account equity"
```

**4. Per-Plan Guardrail Scoping (P2)**
All guardrail queries (daily order limit, max positions, PDT checks) must filter by `plan_id` on the `plan_trades` table — not the global `trades` table. Otherwise one active plan's trades count against another plan's limits.

**5. Global Execution Lock (P2)**
Keep the single global `_cycle_lock` for all Alpaca order execution. Do NOT introduce per-plan locks. Two plans placing simultaneous orders against one account = race condition.

### Trading Cycle Changes

**Current**: `run_cycle()` → one Claude call → one decision → execute

**New Architecture** (parallel Claude, sequential execution):

```python
async def run_all_plans(db):
    # 1. Shared data fetch (once for all plans)
    positions, balance = await asyncio.gather(
        broker.get_positions(), broker.get_account_balance()
    )
    quotes, news, indicators, sectors = await asyncio.gather(
        market_data.get_quotes(...), market_data.get_news(...),
        get_indicators(...), get_sector_signals()
    )

    # 2. Filter active plans matching this schedule time
    active_plans = get_plans_for_current_schedule(db)

    # 3. Parallel Claude calls (2-5s total, not 6-15s sequential)
    plan_decisions = await asyncio.gather(*[
        claude_brain.get_trade_decision(
            positions=compute_plan_positions(db, plan),
            cash_available=plan.virtual_cash,
            market_data=quotes, news=news,
            guardrails_config=plan_to_guardrails(plan),
            technicals_csv=technicals_csv,
            sector_csv=sector_csv,
            earnings_csv=earnings_csv,
        )
        for plan in active_plans
    ])

    # 4. Sequential execution (global lock protects Alpaca + virtual cash)
    results = []
    for plan, decisions in zip(active_plans, plan_decisions):
        async with _execution_lock:
            result = await execute_plan_trades(db, plan, decisions, balance)
            results.append(result)

    return results
```

### Research Insights: Scheduling

- **One APScheduler job per plan** — isolates failures (if Plan A's Claude call fails, Plan B still runs)
- **Use `jitter=60`** — when multiple plans target 9:35 AM, spread them across ±60 seconds to reduce thundering herd
- **`max_instances=1`** per job — prevents duplicate runs of the same plan
- **Error listener** — log plan-specific failures without blocking others:
  ```python
  scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)
  ```
- **Rate limiting**: asyncio Semaphore(3) gates concurrent API calls across all plans

### Research Insights: Cost Analysis

| Frequency | Claude calls/day | Cost/day | Cost/month |
|-----------|-----------------|----------|------------|
| 1x, 3 plans | 3 | $0.015 | $0.30 |
| 3x, 3 plans | 9 | $0.045 | $0.90 |
| 5x, 3 plans | 15 | $0.075 | $1.50 |

For a $200 account, $1.50/month in API costs means you need >0.75% monthly returns just to break even on API costs at 5x frequency. **Recommendation: start with 1x frequency for all plans.**

Optimization: cache a "no-trade" decision when market conditions are flat — skip Claude call if technicals haven't changed since last cycle.

### Frontend Pages

**Plans Overview (`/plans`)**
- Donut chart (Recharts PieChart with `innerRadius={60}`) showing budget allocation
- Card per plan: name, goal icon, budget, P&L, active/paused status
- "Create New Plan" button
- Total portfolio value = sum of all plans
- Clicking a slice navigates to plan detail

**Plan Detail (`/plans/[id]`)**
- Plan-specific dashboard: value, virtual cash, positions, P&L
- Trade history for this plan only (from `plan_trades`)
- Plan settings (goal, risk, frequency, timeline goal)
- Pause/resume toggle
- Delete plan (with confirmation — archives trades, releases budget)

**Create Plan (`/plans/new`)**
- Name input
- Budget amount (with validation: remaining = account_equity - SUM(existing budgets))
- Goal selection (reuse existing goal picker from settings)
- Risk profile (reuse existing picker)
- Frequency
- Optional timeline goal (target amount + date)

### Research Insights: Pie Chart UI

- Use **donut layout** (not solid pie) — modern fintech standard, center can show total value
- **Recharts PieChart** with `paddingAngle={2}` for slice separation
- **Limit to 5-6 slices** — avoid tiny slivers
- Hover dims inactive slices (`opacity` toggle via `activeIndex` state)
- Click slice to navigate to plan detail
- Mobile: stack legend vertically below, reduce `outerRadius`
- Use semantic color tokens from the design system

### API Endpoints

```
GET    /plans              # List all plans with summary stats
POST   /plans              # Create new plan (validates budget sum <= equity)
GET    /plans/:id          # Plan detail with virtual positions + recent trades
PATCH  /plans/:id          # Update settings (re-validates budget sum)
DELETE /plans/:id          # Archive trades, release budget
GET    /plans/:id/trades   # Trade history for plan
POST   /plans/:id/run      # Manual trigger for one plan
GET    /plans/:id/export   # CSV export for plan trades
```

### Migration Path

- Existing trades (pre-plans) remain in the `trades` table as-is
- A "Default Plan" is auto-created with the current budget/goal/risk/frequency settings
- Default plan's budget = current Alpaca account equity
- New "Plans" nav item added in the Trading section of the sidebar
- Old Settings page becomes the "Default Plan" settings (or redirects to `/plans/default`)
- Global kill switch still works — halts ALL plans

### Edge Cases

1. **Budget exceeds account value**: Atomic validation on create/update — `SUM(budgets) <= equity`
2. **Overlapping positions**: Two plans buy AAPL — each tracked via PlanTrade. Virtual position = `SUM(buy_qty) - SUM(sell_qty)` per plan per ticker
3. **Selling from wrong plan**: Pre-sell validation — `plan_virtual_qty >= sell_qty`. Blocks if insufficient
4. **Account value drops below budgets**: Market losses cause real equity < SUM(budgets). Daily reconciliation flags this. Buys blocked until reconciled.
5. **Fractional shares**: Alpaca supports via `notional` order param. Quantity stored as float.
6. **Plan deletion**: Archives trades (soft delete), releases budget back to available pool
7. **Concurrent plan execution**: Global `_execution_lock` serializes Alpaca orders. Claude calls run in parallel.

### Implementation Phases

- [ ] **Phase 1: Data model + CRUD** — Plan/PlanTrade/PlanSnapshot models, migrations, CRUD API, plan list page, budget validation
- [ ] **Phase 2: Per-plan trading** — PlanExecutor with virtual cash, per-plan Claude calls (parallel), global execution lock, PlanTrade logging, security guardrails (overallocation, position theft)
- [ ] **Phase 3: Plan dashboard** — Per-plan detail page with virtual positions, trades, P&L, settings editor
- [ ] **Phase 4: Plan snapshots + analytics** — Daily snapshots per plan, equity curves, per-plan Sharpe/Sortino
- [ ] **Phase 5: Polish** — Donut chart overview, plan CSV export, plan comparison view, Default Plan migration

## Acceptance Criteria

- [ ] User can create 2-3 plans with different goals and budgets
- [ ] Budget validation prevents total allocations from exceeding account equity
- [ ] Each plan runs independently in trading cycles with its own Claude context
- [ ] Plans share one Alpaca account but track virtual cash separately
- [ ] Sell orders validated against plan's virtual position (no cross-plan theft)
- [ ] Per-plan trade history and P&L are isolated
- [ ] Dashboard shows both per-plan and total portfolio views
- [ ] Small budgets ($50-100 per plan) work with fractional shares via notional orders
- [ ] Existing trades migrate to a "Default Plan"
- [ ] Global kill switch halts all plans
- [ ] Claude API calls run in parallel across plans
