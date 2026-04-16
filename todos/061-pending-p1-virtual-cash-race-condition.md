---
status: pending
priority: p1
issue_id: "061"
tags: [code-review, security, plans, concurrency]
dependencies: []
---

# Virtual cash race condition — concurrent runs can double-spend

## Problem Statement
`_execution_lock` in `plans/executor.py` only wraps the Alpaca order call, not the `plan.virtual_cash` read/write. Two concurrent `POST /plans/:id/run` calls (or scheduler + manual trigger) for the same plan both read `plan.virtual_cash`, execute trades, and commit — the second commit overwrites the first's deduction. Cash is effectively duplicated.

## Findings
- `backend/app/plans/executor.py:107` — `remaining_cash = plan.virtual_cash` (unlocked read)
- `backend/app/plans/executor.py:243` — `plan.virtual_cash = remaining_cash` (unlocked write)
- Lock at line 23 is asyncio-only; fails in multi-worker Railway deploys

## Proposed Solution
Options:
1. Per-plan asyncio lock registry keyed by plan_id
2. `SELECT ... FOR UPDATE` on the Plan row at cycle start
3. Optimistic-lock version column (increment on each update, retry on mismatch)

Also wrap `run_plan_cycle` in a single outer lock per plan to prevent scheduler + manual trigger races.

## Acceptance Criteria
- [ ] Two concurrent runs of the same plan can't double-spend
- [ ] Works across multiple uvicorn workers
- [ ] Test with concurrent POST /plans/1/run requests
