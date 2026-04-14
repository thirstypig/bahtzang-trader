---
status: complete
priority: p2
issue_id: "032"
tags: [code-review, architecture, maintainability]
dependencies: []
---

# Trading Goals Defined in 3 Separate Files — Drift Risk

## Problem Statement

Trading goal definitions exist in three locations with different data. Adding a 7th goal requires editing 3 files across 2 languages with no sync enforcement.

**Found by:** Architecture strategist (HIGH), Code simplicity reviewer (MEDIUM)

## Findings

- `backend/app/guardrails.py:47-78` — TRADING_GOALS: label, recommended_frequency, recommended_risk
- `backend/app/claude_brain.py:46-98` — GOAL_PROMPTS: detailed prompt text per goal
- `frontend/src/app/settings/page.tsx:41-104` — TRADING_GOALS: label, icon, description, returns, tickers
- `recommended_risk` field is never consumed (dead data)
- `label` field is never consumed by frontend (hardcodes its own)
- Frontend descriptions may drift from what Claude actually receives
- No compile-time or runtime check that all three dicts carry same keys

## Proposed Solutions

### Option A: Add startup assertion + strip dead data
```python
assert set(TRADING_GOALS.keys()) == set(GOAL_PROMPTS.keys()), "Goal key mismatch"
```
Remove `recommended_risk` and `label` from `TRADING_GOALS`. Derive `VALID_GOALS` from `GOAL_PROMPTS.keys()`.

### Option B: Consolidate into single backend definition + API endpoint
Enrich backend `TRADING_GOALS` with display metadata, have frontend fetch from `/guardrails/presets`.

- **Effort:** Small (A) / Medium (B)
- **Risk:** Low
