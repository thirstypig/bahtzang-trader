---
status: complete
priority: p2
issue_id: "028"
tags: [code-review, logic-bug, guardrails]
dependencies: []
---

# Portfolio Value Reconstruction Always Defaults to $100k

## Problem Statement

The guardrails POST handler tries to reverse-engineer portfolio value from saved config, but `max_portfolio_pct` is never stored in `guardrails.json`. The conditional always evaluates to False, so portfolio value is always $100k regardless of actual portfolio size.

**Found by:** Python reviewer (P2), Architecture strategist (MEDIUM), Code simplicity reviewer (LOW)

## Findings

- `backend/app/routes/guardrails.py:40-42` — `if "max_portfolio_pct" in current` always False
- `max_portfolio_pct` only exists in `RISK_PRESETS` dict, never saved to config
- Switching risk profiles always computes limits based on $100k
- User with $50k or $200k portfolio gets wrong limits

## Proposed Solutions

Simplify to hardcoded $100k (honest) or fetch from broker:

```python
# Option A: Honest default
portfolio_value = 100000

# Option B: Fetch from broker (better)
balance = await broker.get_account_balance()
portfolio_value = balance["total_value"]
```

- **Effort:** Small
- **Risk:** Low
