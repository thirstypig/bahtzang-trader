---
status: pending
priority: p2
issue_id: "071"
tags: [code-review, data-integrity, plans, schema]
dependencies: []
---

# Money fields use Float — floating-point drift in financial ledger

## Problem Statement
All money columns (budget, virtual_cash, price, virtual_cash_before/after, invested_value, total_value, pnl) use `Float` which is IEEE 754 double precision. Python float arithmetic accumulates errors like `0.1 + 0.2 == 0.30000000000000004`. Over thousands of trades, cents drift. For a trading app this is technically incorrect.

## Findings
- `backend/app/plans/models.py` — all money fields are Float
- `backend/app/plans/executor.py:197-199` — `remaining_cash -= trade_value` uses Python float arithmetic

## Proposed Solution
Convert to `Numeric(precision=14, scale=4)` which gives exact decimal arithmetic:
```python
budget: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
```

Use Python's `Decimal` in the executor:
```python
from decimal import Decimal
remaining_cash = Decimal(str(plan.virtual_cash))
```

This is a larger refactor — might be deferred if current scale is small enough.

## Acceptance Criteria
- [ ] All money columns use Numeric
- [ ] Python code uses Decimal
- [ ] No string/float conversion drift
