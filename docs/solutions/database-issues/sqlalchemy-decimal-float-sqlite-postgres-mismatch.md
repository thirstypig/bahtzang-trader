---
name: SQLAlchemy Decimal/float type mismatch between SQLite and PostgreSQL
description: SQLAlchemy func.sum() on Numeric columns returns Decimal in PostgreSQL but float in SQLite, causing TypeError in production while tests pass silently
type: database-issue
severity: critical
component: plans/routes.py, plans/executor.py, database
tags: [sqlite, postgresql, type-coercion, sqlalchemy, numeric-decimal, production-only, test-environment-mismatch]
date: 2026-05-08
status: resolved
---

# SQLAlchemy Decimal/float Mismatch: SQLite Tests Pass, PostgreSQL Production Crashes

## Problem

Creating a new portfolio via `POST /portfolios/new` returned a browser-level "Failed to fetch" error — no HTTP status code, just a dropped TCP connection. The UI showed nothing actionable.

Railway logs revealed:

```
TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'
  File "app/plans/routes.py", line 142, in _validate_budget
    if new_budget + _total_budgets(db, exclude_plan_id=exclude_id) > equity:
```

All 285 backend tests passed. The bug was invisible in CI.

## Root Cause

`_total_budgets()` called `func.sum(Portfolio.budget)` against a `Numeric(14,4)` column. The return type of `func.sum()` depends on the database driver:

| Environment | DB | `func.sum()` return type |
|---|---|---|
| Tests (CI) | SQLite in-memory | `float` |
| Production | PostgreSQL (Supabase) | `decimal.Decimal` |

Python's `decimal` module **deliberately refuses** mixed `Decimal + float` arithmetic to prevent silent precision loss:

```python
>>> from decimal import Decimal
>>> Decimal("1500.00") + 200.0
TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'
```

The type annotation `-> float` on `_total_budgets()` was aspirational, not enforced. mypy would catch this, but the project does not run mypy in CI.

Because `uvicorn` treats unhandled exceptions as fatal for the request, the TCP connection is dropped rather than returning a 500 — the browser sees "Failed to fetch" with no status code.

## Fix

Cast the ORM result to `float` explicitly at the SQLAlchemy boundary:

```python
# Before (production crash)
def _total_budgets(db: Session, exclude_plan_id: int | None = None) -> float:
    q = db.query(func.coalesce(func.sum(Portfolio.budget), 0.0))
    if exclude_plan_id is not None:
        q = q.filter(Portfolio.id != exclude_plan_id)
    return q.scalar()  # returns Decimal in production!

# After (fixed)
def _total_budgets(db: Session, exclude_plan_id: int | None = None) -> float:
    q = db.query(func.coalesce(func.sum(Portfolio.budget), 0.0))
    if exclude_plan_id is not None:
        q = q.filter(Portfolio.id != exclude_plan_id)
    return float(q.scalar() or 0)  # explicit cast at ORM boundary
```

`float(q.scalar() or 0)` handles three cases:
1. Normal result: `Decimal("1500.00")` → `1500.0` ✓
2. No rows (`None`): `None or 0` → `0`, then `float(0)` → `0.0` ✓
3. Zero sum: `Decimal("0")` → `0.0` ✓

## Why Tests Didn't Catch It

The test suite uses SQLite with `StaticPool` (defined in `tests/conftest.py`). SQLite's `SUM()` aggregate over a `REAL` column returns a Python `float`. The same code path that returns `Decimal` in PostgreSQL returns `float` in SQLite — so the arithmetic `new_budget + _total_budgets(...)` works in tests and crashes in production.

This is a classic **ORM type-return divergence**: column type declarations in SQLAlchemy models describe the logical type, not the Python type that comes back from aggregate functions. Aggregates bypass the column type mapper.

## Related Documentation

- [`sqlite-datetime-timezone-stripping.md`](sqlite-datetime-timezone-stripping.md) — The same root pattern: SQLite's test environment silently handles types differently than PostgreSQL production. Timezone-aware datetimes come back naive from SQLite.
- [`supabase-batch-migration-silent-failure.md`](supabase-batch-migration-silent-failure.md) — Another production-only failure invisible to tests: Supabase's batch migration path differs from SQLite DDL behavior.

## Prevention

### Rule: Cast at Every ORM Aggregate Boundary

Any call to `func.sum()`, `func.avg()`, `func.count()`, or `func.coalesce()` that feeds into Python arithmetic **must** be explicitly cast. Never rely on the declared column type — aggregates bypass it.

```python
# Convention: to_float() helper at ORM boundary
def to_float(val) -> float:
    """Cast ORM aggregate result to float. Handles Decimal, None, int."""
    return float(val) if val is not None else 0.0
```

Add this to `backend/app/database.py` and import it wherever aggregate results flow into arithmetic.

### Regression Test

Add to `tests/plans/test_plan_routes.py`:

```python
def test_create_portfolio_tolerates_decimal_budget_sum(client, db):
    """Ensure _total_budgets() does not return Decimal in any DB backend."""
    from decimal import Decimal
    from app.plans.routes import _total_budgets

    # Create a portfolio with a Decimal-like budget
    p = Portfolio(name="seed", budget=Decimal("1000.0"), ...)
    db.add(p)
    db.commit()

    result = _total_budgets(db)
    assert isinstance(result, float), f"Expected float, got {type(result)}"
    assert result == 1000.0
```

This test passes on SQLite today (where the bug is invisible) — but serves as documentation of the invariant and will catch regressions if the ORM layer ever changes.

### Audit: Other Vulnerable Sites

The following aggregate call sites in the codebase have the same exposure. They have not yet caused production crashes but should be hardened:

| File | Line range | Aggregate | Used in arithmetic? | Risk |
|---|---|---|---|---|
| `plans/routes.py` | `_total_budgets()` | `func.sum(Portfolio.budget)` | Yes (`+ new_budget`) | **Fixed** |
| `plans/routes.py` | `~275-289` | `func.sum(Trade.quantity * Trade.price)` / `func.sum(Trade.quantity)` | Yes (division for avg cost) | **Fixed** |
| `plans/executor.py` | `~43-55` | `func.sum(case(...))` for `net_qty` | Yes (position sizing) | **Fixed** |
| `analytics.py` | snapshot metrics | _(audited — no func.sum/avg/coalesce calls present)_ | N/A | ✅ Clean |

All identified high-risk sites have been hardened. A full grep of `analytics.py` confirmed it contains no SQLAlchemy aggregate calls; the entry was a false alarm from static analysis.

### Detection

To find all remaining unguarded aggregate sites:

```bash
grep -rn "func\.sum\|func\.avg\|func\.coalesce" backend/app/ \
  | grep -v "test_" \
  | grep -v "float("
```

Any match that participates in arithmetic should be audited.
