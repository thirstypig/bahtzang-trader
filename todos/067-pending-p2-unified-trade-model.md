---
status: pending
priority: p2
issue_id: "067"
tags: [code-review, architecture, plans, data-model]
dependencies: [062]
---

# Trade and PlanTrade are 85% duplicate — unify

## Problem Statement
`Trade` and `PlanTrade` share the same columns with minor differences. Having both means:
- Tax export via `/trades/export` misses plan trades
- Analytics/reporting must run twice
- Bug fixes need to be applied twice (the recent JSON reasoning fix is a good example)

## Findings
- `backend/app/models.py:16` — Trade table
- `backend/app/plans/models.py:53` — PlanTrade table, 85% identical
- Divergences: `Trade.quantity` is Integer vs PlanTrade Float (fractional), PlanTrade has `plan_id` + `virtual_cash_before/after`

## Proposed Solution
Unify to one Trade table with:
- `plan_id: Integer | None` (NULL = legacy/global)
- `quantity: Float` (promote for fractional support)
- `virtual_cash_before: Float | None`
- `virtual_cash_after: Float | None`

Migration:
1. Add columns to Trade table
2. Copy PlanTrade rows into Trade
3. Update queries to filter `plan_id IS NOT NULL` or `plan_id = ?`
4. Drop PlanTrade table

## Acceptance Criteria
- [ ] Single Trade table
- [ ] Migration preserves all historical data
- [ ] Both `/trades` and `/plans/:id/trades` work
- [ ] Tax export includes plan trades
