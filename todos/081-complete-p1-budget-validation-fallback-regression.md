---
status: complete
priority: p1
issue_id: "081"
tags: [code-review, security, plans, regression]
dependencies: []
---

# Budget validation falls back to $10M cap when broker unreachable

## Problem Statement
Fix 060 was meant to eliminate the hardcoded $10M budget cap by validating against real Alpaca equity. But `_validate_budget` catches broker errors and falls back to `real_equity = 10_000_000` — silently resurrecting the exact value 060 was designed to eliminate. If Alpaca is temporarily down, a user could create a $10M plan.

## Findings
- `backend/app/plans/routes.py:54-78` — `_validate_budget` has `except Exception: real_equity = 10_000_000`

## Proposed Solution
Fail closed: return 503 when the broker is unreachable, don't create the plan.
```python
try:
    balance = await broker.get_account_balance("default")
    real_equity = balance.get("total_value", 0)
except Exception as e:
    logger.warning("Broker unreachable for budget validation: %s", e)
    raise HTTPException(status_code=503, detail="Cannot validate budget — broker temporarily unavailable")
```

## Acceptance Criteria
- [ ] Plan creation rejected when broker fails
- [ ] No magic numbers in validation
