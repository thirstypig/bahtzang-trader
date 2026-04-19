---
status: pending
priority: p2
issue_id: "096"
tags: [code-review, backend, security]
dependencies: []
---

# Security Hardening: setattr Guard, Query Bounds, Error Leaks, Rate Limit

## Problem Statement

Four related security findings from the security sentinel review, grouped for efficient resolution:

1. **Mass assignment fragility** (`routes.py:269`): `setattr(plan, key, value)` loop is safe today because `PlanUpdate` excludes `virtual_cash`, but fragile if someone adds it later.

2. **Unbounded query params** (`routes.py:367`): `limit` and `days` parameters have no upper bounds. `?limit=999999999` could cause memory exhaustion.

3. **Error message leaks** (`earnings/routes.py:56`): `str(e)` returned to client could leak DB connection strings, file paths, etc.

4. **Missing rate limit on plan run** (`routes.py:320`): `POST /plans/{plan_id}/run` has no specific rate limit. The global `60/minute` is too permissive for real-money trade triggers. Compare: `POST /run` correctly has `2/minute`.

## Proposed Solutions

### Fix 1: Add IMMUTABLE_FIELDS guard
```python
IMMUTABLE_FIELDS = {"id", "created_at", "virtual_cash"}
for key, value in updates.items():
    if key not in IMMUTABLE_FIELDS:
        setattr(plan, key, value)
```

### Fix 2: Add Query() bounds
```python
limit: int = Query(100, ge=1, le=500)
days: int = Query(90, ge=1, le=365)
```

### Fix 3: Sanitize error response
```python
except Exception as e:
    logger.error("Earnings refresh failed: %s", e)
    raise HTTPException(500, "Earnings refresh failed. Check server logs.")
```

### Fix 4: Add rate limit
```python
@router.post("/{plan_id}/run")
@limiter.limit("2/minute")
async def run_plan(request: Request, ...):
```

- **Effort:** Small (all four are quick fixes)
- **Risk:** Low

## Acceptance Criteria

- [ ] `setattr` loop excludes immutable fields
- [ ] All `limit` and `days` params have upper bounds
- [ ] No raw exception messages returned to client in any endpoint
- [ ] `POST /plans/{plan_id}/run` has `2/minute` rate limit

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from security sentinel review | No Critical/High findings — solid security baseline |
