---
status: complete
priority: p3
issue_id: "087"
tags: [code-review, plans, simplicity]
dependencies: []
---

# Simplify run_plan_cycle wrapper/_locked split

## Problem Statement
The outer `run_plan_cycle` / inner `_run_plan_cycle_locked` split adds 30 lines of duplicated 9-parameter signature and a separate docstring, solely to wrap `async with` around the body. Only one caller exists.

## Findings
- `backend/app/plans/executor.py:71-109` — wrapper split

## Proposed Solution
Inline the lock:
```python
async def run_plan_cycle(db, plan, positions, ...):
    async with _get_plan_lock(plan.id):
        db.refresh(plan)
        # ... existing body ...
        return results
```

Removes ~25 LOC, one function, one docstring.

## Acceptance Criteria
- [ ] Single run_plan_cycle function with inlined lock
- [ ] No behavior change
