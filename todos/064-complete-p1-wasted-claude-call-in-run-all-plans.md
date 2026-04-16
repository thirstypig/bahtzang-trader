---
status: complete
priority: p1
issue_id: "064"
tags: [code-review, performance, plans, cost]
dependencies: []
---

# run_all_plans makes wasted Claude API calls — costs $X/month

## Problem Statement
`run_all_plans` uses `asyncio.gather` to parallelize Claude calls for all plans, but the results are DISCARDED. It then calls `run_plan_cycle` for each plan, which makes its OWN Claude call. So every scheduled cycle makes 2N Claude calls instead of N. At 5x/day with 3 plans, that's 30 wasted calls/day = $3-9/month of burned API cost.

## Findings
- `backend/app/plans/executor.py:291-308` — `plan_decisions = await asyncio.gather(...)` — never used
- `backend/app/plans/executor.py:316` — `results = await run_plan_cycle(...)` — makes its own Claude call

## Proposed Solution
Either:
1. **Delete the gather** — `run_plan_cycle` already makes its own call. Net savings: 50% API cost, simpler code.
2. **Pass decisions down** — Change `run_plan_cycle` to accept pre-computed decisions:
   ```python
   async def run_plan_cycle(db, plan, decisions, positions, balance, quotes, ...):
       # Skip the Claude call, use decisions
   ```

Option 1 is simpler and has lower latency for per-plan `POST /plans/:id/run`. Option 2 keeps the parallelism benefit for the scheduled cycle.

## Acceptance Criteria
- [ ] Cycle makes exactly N Claude calls for N plans, not 2N
- [ ] Cost analysis confirms reduction
