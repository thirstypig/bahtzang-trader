---
status: pending
priority: p3
issue_id: "100"
tags: [code-review, backend, frontend, cleanup]
dependencies: []
---

# Remove Dead Code: Unused Endpoints, return_pct, Unused Index

## Problem Statement

Several pieces of code are built but never used:

1. **`/plans/{plan_id}/metrics` endpoint** (`routes.py:419-474`, 56 LOC) — never called from frontend. `getPlanMetrics` in `api.ts:358-363` is exported but never imported anywhere.

2. **`/plans/{plan_id}/trades` endpoint** (`routes.py:364-383`, 20 LOC) — standalone trade history endpoint never called. Trades are already embedded in the `get_plan` response (line 166-173).

3. **`return_pct`** (`PlanEquityCurve.tsx:74`) — computed for every snapshot but never rendered in the chart.

4. **`ix_plan_trades_timestamp_desc` index** (`models.py:89`) — sorts only by `timestamp DESC` with no plan filter. All actual queries filter by `plan_id` first, making this index unused. Costs write performance for no read benefit.

## Proposed Solutions

Remove all four. Total: ~84 LOC removed.

- **Effort:** Small
- **Risk:** Low (index removal requires migration awareness)

## Acceptance Criteria

- [ ] Unused endpoints and API functions removed
- [ ] `return_pct` computation removed from PlanEquityCurve data mapping
- [ ] Unused index removed (note: requires Alembic migration or manual DROP INDEX)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from code simplicity reviewer | ~84 LOC removable |
