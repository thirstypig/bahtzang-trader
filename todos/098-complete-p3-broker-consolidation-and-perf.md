---
status: pending
priority: p3
issue_id: "098"
tags: [code-review, backend, architecture, performance]
dependencies: []
---

# Backend Cleanup: AlpacaBroker Consolidation, Quote Lookup, Cache Headers

## Problem Statement

Three related backend cleanup items:

1. **AlpacaBroker proliferation**: 3+ separate `AlpacaBroker()` instances across `executor.py:20`, `routes.py:22`, `routes.py:341`. Functionally harmless (underlying client is singleton), but confusing and risky if broker gains state.

2. **Linear scan for quote lookup** (`executor.py:118-120, 146-148`): `next((q for q in quotes if q["ticker"] == ticker), 0)` is O(T) per ticker inside a loop. Should use a dict lookup like `routes.py:219` already does.

3. **Missing cache headers for /plans routes** (`main.py:51-69`): Cache header middleware has rules for `/portfolio`, `/trades`, `/earnings`, `/backtest` but nothing for `/plans`. Plan snapshots would benefit from `max-age=300`.

## Proposed Solutions

1. Use module-level `_broker` in `run_plan` instead of creating a new instance
2. Build `price_map = {q["ticker"]: q["price"] for q in quotes}` once at the start of `_execute_plan_cycle`
3. Add `elif path.startswith("/plans") and "/run" not in path and "/export" not in path: max-age=60`

- **Effort:** Small (all three are quick)
- **Risk:** Low

## Acceptance Criteria

- [ ] Single AlpacaBroker instance in `routes.py`
- [ ] Quote lookups use dict, not linear scan
- [ ] `/plans` GET endpoints have appropriate cache headers

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from Python reviewer, performance oracle, architecture strategist | |
