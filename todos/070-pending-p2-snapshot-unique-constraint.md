---
status: pending
priority: p2
issue_id: "070"
tags: [code-review, data-integrity, plans, schema]
dependencies: []
---

# PlanSnapshot has no unique constraint on (plan_id, date)

## Problem Statement
The daily snapshot job upserts based on "does today's row exist?" but there's no unique constraint enforcing this at DB level. Two concurrent snapshot jobs would both see no existing row and both INSERT, producing duplicates.

## Findings
- `backend/app/plans/models.py:114-116` — only a non-unique `Index("ix_plan_snapshots_plan_date", ...)` exists
- `backend/app/plans/snapshots.py:60-82` — upsert logic assumes no duplicates

## Proposed Solution
```python
__table_args__ = (
    Index("ix_plan_snapshots_plan_date", "plan_id", date.desc()),
    UniqueConstraint("plan_id", "date", name="uq_plan_snapshots_plan_date"),
)
```

Also run `ALTER TABLE plan_snapshots ADD CONSTRAINT uq_plan_snapshots_plan_date UNIQUE (plan_id, date)` in production.

## Acceptance Criteria
- [ ] Unique constraint added to schema
- [ ] Migration run in production
- [ ] Duplicate snapshots impossible
