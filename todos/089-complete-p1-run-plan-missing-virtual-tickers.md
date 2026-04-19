---
status: pending
priority: p1
issue_id: "089"
tags: [code-review, backend, plans, financial-safety]
dependencies: []
---

# run_plan Route Missing Virtual-Position Tickers

## Problem Statement

The `POST /plans/{plan_id}/run` endpoint (manual "Run Now" button) fetches market data only for tickers held in the Alpaca account, not for tickers held in the plan's virtual positions. If a plan holds virtual positions in tickers not reflected in the Alpaca merged view, those tickers get no quote — Claude makes decisions with incomplete data.

**Why it matters:** Financial decision quality depends on complete market data. Missing quotes for held positions means Claude cannot evaluate whether to hold or sell them.

## Findings

- **Source:** Python Reviewer, Architecture Strategist (confirmed independently)
- `routes.py:346` — `held_tickers = [p.get("instrument", {}).get("symbol", "") for p in positions]` only includes Alpaca account positions
- `executor.py:338-343` — `run_all_plans` correctly unions virtual position tickers via `compute_virtual_positions(db, plan.id).keys()`
- The `run_plan` route duplicates ~30 lines of market data fetching from `run_all_plans` without the ticker union logic

## Proposed Solutions

### Option A: Extract shared market data fetching (Recommended)
- Create `fetch_shared_market_data(db, plan_ids)` in `executor.py`
- Both `run_all_plans` and `run_plan` call it
- **Pros:** DRY, ensures both paths stay in sync
- **Cons:** Slightly more refactoring
- **Effort:** Small
- **Risk:** Low

### Option B: Inline the ticker union in run_plan
- Add `compute_virtual_positions(db, plan_id).keys()` to the ticker set in `run_plan`
- **Pros:** Minimal change
- **Cons:** Leaves the duplication in place
- **Effort:** Trivial
- **Risk:** Low

## Recommended Action

Option A — extract and share the function.

## Technical Details

- **Affected files:** `backend/app/plans/routes.py`, `backend/app/plans/executor.py`
- **Components:** Plan execution, market data fetching

## Acceptance Criteria

- [ ] Manual "Run Now" fetches quotes for all virtual position tickers, not just Alpaca account positions
- [ ] Market data fetching logic is shared between `run_plan` and `run_all_plans`
- [ ] No duplicate broker instantiation in `run_plan` (currently creates a new `AlpacaBroker()` on line 341)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from multi-agent code review | Python reviewer + architecture strategist both flagged independently |
