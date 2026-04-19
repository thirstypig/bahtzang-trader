---
status: pending
priority: p2
issue_id: "092"
tags: [code-review, backend, plans, financial-safety]
dependencies: []
---

# update_plan Budget Reduction Creates Inconsistent Virtual Cash

## Problem Statement

When reducing a plan's budget below the currently invested amount, `virtual_cash` goes to 0 via `max(0, ...)`, but the actual virtual positions are worth more than the new budget. This creates a state where `invested > budget`.

Example: budget=10000, virtual_cash=2000, invested=8000. Reduce budget to 5000 → virtual_cash=max(0, 2000-5000)=0, but positions are still worth $8000. Plan shows budget=5000, invested=5000, but real positions = $8000.

## Findings

- **Source:** Python Reviewer
- `routes.py:261-266` — `plan.virtual_cash = max(0, plan.virtual_cash + budget_diff)`
- No validation that `new_budget >= (budget - virtual_cash)`

## Proposed Solutions

Add validation: reject budget reductions below currently invested amount:
```python
invested = plan.budget - plan.virtual_cash
if new_budget < invested:
    raise HTTPException(400, f"Cannot reduce budget below invested amount (${invested:,.2f})")
```

- **Effort:** Trivial
- **Risk:** Low

## Acceptance Criteria

- [ ] Budget cannot be reduced below currently invested amount
- [ ] Clear error message explains the constraint

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from Python reviewer | |
