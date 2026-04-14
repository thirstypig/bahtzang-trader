---
status: complete
priority: p2
issue_id: "036"
tags: [code-review, logic-bug, guardrails]
dependencies: []
---

# apply_risk_preset() Returns Incomplete Config

## Problem Statement

`apply_risk_preset()` returns a dict without `trading_goal` or `trading_frequency` keys. Code calling it directly (not through `load_guardrails()`) loses these settings. The route handler patches them back manually, but this coupling is fragile.

**Found by:** Python reviewer (P2)

## Findings

- `backend/app/guardrails.py:97-109` — No `trading_goal` or `trading_frequency` in return value
- `backend/app/guardrails.py:126` — Fallback path calls `apply_risk_preset("moderate")` without defaults
- `backend/app/routes/guardrails.py:46-47` — Route manually patches them back
- Any new caller of `apply_risk_preset()` would silently lose goal/frequency

## Proposed Solutions

Add defaults to `apply_risk_preset()`:
```python
return {
    "risk_profile": profile,
    "trading_goal": "maximize_returns",
    "trading_frequency": "1x",
    ...existing fields...
}
```

- **Effort:** Small (2 lines)
- **Risk:** None
