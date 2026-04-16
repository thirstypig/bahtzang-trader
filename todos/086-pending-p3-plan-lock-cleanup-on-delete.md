---
status: pending
priority: p3
issue_id: "086"
tags: [code-review, plans, memory]
dependencies: []
---

# _plan_locks grows unbounded — evict on plan delete

## Problem Statement
The `_plan_locks` dict in `plans/executor.py` adds a new asyncio.Lock() per plan_id but never evicts. Deleted plans leave stale locks in the dict.

Real memory impact is minimal (few hundred bytes per lock), but it's a true leak.

## Findings
- `backend/app/plans/executor.py:22-31` — `_get_plan_lock` only inserts, never pops

## Proposed Solution
In `backend/app/plans/routes.py` `delete_plan`, after successful commit:
```python
from app.plans.executor import _plan_locks
_plan_locks.pop(plan_id, None)
```

## Acceptance Criteria
- [ ] Deleted plans release their lock entries
