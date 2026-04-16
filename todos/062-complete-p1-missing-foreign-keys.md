---
status: complete
priority: p1
issue_id: "062"
tags: [code-review, data-integrity, plans, schema]
dependencies: []
---

# PlanTrade/PlanSnapshot have no foreign key to Plan — silent orphans

## Problem Statement
`PlanTrade.plan_id` and `PlanSnapshot.plan_id` are plain Integer columns without ForeignKey constraints. When a plan is deleted, its trades and snapshots become orphans pointing to nonexistent plans. No cascade behavior is defined. This is the worst of both worlds — no referential integrity AND no explicit preservation semantics.

## Findings
- `backend/app/plans/models.py:57` — `plan_id: Mapped[int] = mapped_column(Integer, nullable=False)` — should be `ForeignKey("plans.id")`
- `backend/app/plans/models.py:105` — same issue on PlanSnapshot
- `DELETE /plans/:id` in `routes.py:239-254` just calls `db.delete(plan)` with no cleanup

## Proposed Solution
Add `ForeignKey("plans.id", ondelete="RESTRICT")` — block deletion when history exists. This forces explicit handling: user must export/archive before deleting, which is correct for financial records.

```python
plan_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
)
```

Alternative: `ondelete="CASCADE"` if we truly want delete to wipe trades (probably wrong for audit).

Also add FK in migration for existing production DB.

## Acceptance Criteria
- [ ] FKs added to both tables
- [ ] DELETE /plans/:id properly handles restricted plans
- [ ] Migration run in production via psql ALTER TABLE
