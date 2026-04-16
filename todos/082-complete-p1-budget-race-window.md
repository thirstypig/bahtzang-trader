---
status: complete
priority: p1
issue_id: "082"
tags: [code-review, security, plans, concurrency]
dependencies: []
---

# Budget validation has read-then-write race window

## Problem Statement
`_validate_budget` does `SELECT SUM(budget)` then `INSERT` without a DB lock or serializable transaction. Two concurrent POST /plans requests can each pass validation, then both insert — overshooting real equity.

## Findings
- `backend/app/plans/routes.py:74-78` — validation and insert not in serializable transaction
- No `SELECT ... FOR UPDATE` on plans table

## Proposed Solution
Wrap validation + insert in a serializable transaction:
```python
db.execute(text("LOCK TABLE plans IN SHARE ROW EXCLUSIVE MODE"))
await _validate_budget(db, budget)
plan = Plan(...)
db.add(plan)
db.commit()
```

Or use a Postgres advisory lock keyed on a constant:
```python
db.execute(text("SELECT pg_advisory_xact_lock(9001)"))
```

## Acceptance Criteria
- [ ] Two concurrent create requests can't both pass validation with insufficient equity
