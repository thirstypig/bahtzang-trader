---
status: complete
priority: p2
issue_id: "065"
tags: [code-review, performance, plans, database]
dependencies: []
---

# N+1 queries in list_plans and positions endpoint

## Problem Statement
Three N+1 query patterns in the plans module:

1. `list_plans` runs one trade count query per plan
2. Positions endpoint loops per-ticker to compute avg_cost
3. `run_all_plans` calls `compute_virtual_positions` once per plan sequentially

## Findings
- `backend/app/plans/routes.py:65-69` — trade_count query per plan
- `backend/app/plans/routes.py:151-165` — avg_cost query per ticker
- `backend/app/plans/executor.py:291-308` — per-plan queries in gather generator

## Proposed Solution

**list_plans**:
```python
counts = dict(db.query(PlanTrade.plan_id, func.count(PlanTrade.id))
              .filter(PlanTrade.executed.is_(True))
              .group_by(PlanTrade.plan_id).all())
# Then merge into plan dicts
```

**positions avg_cost**:
```python
rows = db.query(
    PlanTrade.ticker,
    (func.sum(PlanTrade.quantity * PlanTrade.price) / func.sum(PlanTrade.quantity)).label("avg_cost")
).filter(
    PlanTrade.plan_id == plan_id,
    PlanTrade.action == "buy",
    PlanTrade.executed.is_(True),
    PlanTrade.price.isnot(None),
).group_by(PlanTrade.ticker).all()
avg_costs = {row.ticker: row.avg_cost for row in rows}
```

**run_all_plans**: Pre-compute all virtual positions in one grouped query.

## Acceptance Criteria
- [ ] list_plans uses single GROUP BY query
- [ ] positions endpoint uses single aggregated query
- [ ] run_all_plans fetches positions once across all plans
