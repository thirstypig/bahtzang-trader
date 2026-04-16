---
status: complete
priority: p1
issue_id: "080"
tags: [code-review, data-integrity, plans, regression]
dependencies: []
---

# PlanTrade missing alpaca_order_id — reconciliation has no anchor

## Problem Statement
Fix 063 added "MANUAL RECONCILIATION NEEDED" logging when a DB commit fails after an Alpaca order succeeded. But the broker's returned `order_id` is discarded — `await broker.place_order(...)` has no assignment. The log message references only ticker/timestamp/qty, so an operator can't pinpoint which Alpaca order actually executed.

This is a regression/incomplete fix — the original 063 proposal explicitly called for an `alpaca_order_id` column.

## Findings
- `backend/app/plans/executor.py:232-237` — `await broker.place_order(...)` result discarded
- `backend/app/plans/models.py` — PlanTrade has no `alpaca_order_id` column
- `backend/app/brokers/alpaca.py:97-101` — broker DOES return `{"status", "order_id", "filled_qty"}`
- `backend/app/plans/executor.py:273-281` — reconciliation log missing order ID

## Proposed Solution
1. Add `alpaca_order_id: Mapped[str | None]` to PlanTrade model
2. Capture broker return: `order = await broker.place_order(...)`; `plan_trade.alpaca_order_id = order["order_id"]`
3. Include in reconciliation log: `logger.exception("RECONCILIATION: Plan %d Alpaca order %s executed but DB failed", plan.id, order["order_id"])`
4. ALTER TABLE plan_trades ADD COLUMN alpaca_order_id VARCHAR(64) in production

## Acceptance Criteria
- [ ] alpaca_order_id captured on every executed trade
- [ ] Reconciliation log includes order ID
- [ ] Production column added
