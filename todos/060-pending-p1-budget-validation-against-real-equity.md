---
status: pending
priority: p1
issue_id: "060"
tags: [code-review, security, plans, data-integrity]
dependencies: []
---

# Budget validation uses $10M hardcoded cap instead of real Alpaca equity

## Problem Statement
`create_plan` and `update_plan` validate that `SUM(budgets) <= 10_000_000` — a hardcoded cap unrelated to the real account. If the Alpaca paper account has $100K but users create plans summing to $500K, the bot will issue orders Alpaca will reject. This was flagged as a P1 gap in the original architecture plan but never closed.

## Findings
- `backend/app/plans/routes.py:84` — `if existing_total + body.budget > 10_000_000`
- `backend/app/plans/routes.py:221` — same hardcoded cap on update
- The original plan (docs/plans/2026-04-15-feat-investment-plans-pie-style-plan.md) explicitly called for `SUM(budgets) <= account_equity` with atomic validation

## Proposed Solution
Fetch real equity from the broker and validate against it:
```python
balance = await broker.get_account_balance("default")
if existing_total + body.budget > balance["total_value"]:
    raise HTTPException(400, f"Would exceed account equity of ${balance['total_value']:,.0f}")
```

Use `SELECT ... FOR UPDATE` on the plans table or a DB-level trigger to prevent concurrent creates from bypassing the check.

## Acceptance Criteria
- [ ] Plan creation rejected if `SUM(budgets) + new > real_equity`
- [ ] Plan update rejected similarly
- [ ] Concurrent plan creates can't bypass validation
