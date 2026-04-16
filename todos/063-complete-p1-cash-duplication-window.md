---
status: complete
priority: p1
issue_id: "063"
tags: [code-review, data-integrity, plans, transactions]
dependencies: []
---

# Cash duplication window — Alpaca order succeeds but DB commit may fail

## Problem Statement
In `run_plan_cycle`, the order is:
1. Place Alpaca order (real money)
2. Mutate `remaining_cash` in memory
3. (Later at end of cycle) Commit DB changes

If the DB commit fails after Alpaca order succeeds (connection drop, crash, disk full), the real order went through but `virtual_cash` is never decremented. Next cycle re-spends the same virtual cash — cash is duplicated.

## Findings
- `backend/app/plans/executor.py:186-209` — Alpaca order placed before commit
- `backend/app/plans/executor.py:244` — single commit for all trades in cycle
- No `try/except` around commit
- No idempotency key on Alpaca orders

## Proposed Solution
Per-trade transaction with commit-immediately-after-Alpaca-success:
```python
async with _execution_lock:
    order = await broker.place_order(...)
    plan_trade = PlanTrade(..., alpaca_order_id=order["order_id"])
    plan.virtual_cash = remaining_cash
    db.add(plan_trade)
    try:
        db.commit()
    except Exception:
        # Alpaca order went through but DB failed — log for manual reconciliation
        logger.error("RECONCILIATION NEEDED: Alpaca order %s executed but DB commit failed", order["order_id"])
        raise
```

Add `alpaca_order_id` column to PlanTrade to enable reconciliation.

## Acceptance Criteria
- [ ] Each trade commits immediately after Alpaca success
- [ ] `alpaca_order_id` stored for reconciliation
- [ ] Commit failure logged loudly for ops attention
