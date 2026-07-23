---
id: DOC-049
type: solution
status: active
phase: null
owner: james
tags: [testing, database]
links: []
updated: 2026-05-08
description: SQLite returns float from func.sum() on Numeric columns while PostgreSQL returns Decimal, making Decimal+float TypeErrors invisible in CI unless isinstance assertions are added alongside value equality checks
severity: medium
component: testing, plans/executor, plans/routes
legacy_type: test-failure
---

# False-Passing Equality Tests: SQLite/PostgreSQL Numeric Type Divergence

## Problem

After fixing a `Decimal + float TypeError` that crashed `POST /portfolios` in production (but was invisible in CI), the existing tests still provided false assurance. Tests like:

```python
assert positions["AAPL"] == 10.0
```

passed on both the broken AND the fixed code. The bug was undetectable from the test results.

The root cause of the false passing: `Decimal("10.0") == 10.0` evaluates to `True` in Python. SQLAlchemy's `func.sum()` on a `Numeric(14,4)` column returns `Decimal` from PostgreSQL (psycopg2) and `float` from SQLite (pysqlite) — and since tests run against SQLite, the downstream `Decimal + float` crash never surfaces in CI.

## Core Insight: Value Equality Cannot Distinguish Numeric Types

```python
from decimal import Decimal

Decimal("5.0") == 5.0   # True  ← Python numeric coercion
isinstance(Decimal("5.0"), float)  # False  ← the real discriminator
```

Standard `assert result == expected` tests pass regardless of whether `result` is `Decimal` or `float`. The only reliable discriminator is `isinstance`.

| Assertion | Decimal("5.0") | 5.0 (float) |
|---|---|---|
| `assert result == 5.0` | ✓ passes | ✓ passes |
| `assert isinstance(result, float)` | ✗ fails | ✓ passes |

## Solution

### 1. Cast at the ORM Boundary (Source Code)

`func.sum()` (and `func.avg()`, `func.coalesce()` over numeric) returns different Python types depending on the DB driver. Normalize immediately at the call site:

```python
# plans/routes.py — _total_budgets()
return float(q.scalar() or 0)           # was: q.scalar() or 0

# plans/routes.py — avg_costs dict
float(r.total_cost) / float(r.total_qty) # was: r.total_cost / r.total_qty

# plans/executor.py — compute_virtual_positions()
{row.ticker: float(row.net_qty) for row in rows ...} # was: row.net_qty directly
```

The `float()` cast belongs at the point where ORM data crosses into application code — not scattered at every downstream call site.

### 2. Add isinstance Assertions in Tests

Pair `isinstance` with value equality whenever the return type matters for downstream arithmetic:

```python
# tests/plans/test_executor.py
def test_values_are_python_float(self, db_session):
    """Position quantities must be float, not Decimal.

    SQLAlchemy func.sum() returns Decimal in PostgreSQL and float in SQLite.
    Decimal("5.0") == 5.0 is True, so value equality alone cannot catch this
    bug — isinstance is required.
    """
    plan = make_plan(db_session)
    make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=5)
    make_trade(db_session, plan.id, ticker="AAPL", action="sell", quantity=2)
    positions = compute_virtual_positions(db_session, plan.id)
    for ticker, qty in positions.items():
        assert isinstance(qty, float), (
            f"{ticker} qty is {type(qty).__name__}, expected float — "
            "Decimal + float arithmetic crashes in production with PostgreSQL"
        )
```

```python
# tests/plans/test_routes.py
@pytest.mark.unit
class TestTotalBudgetsReturnType:
    """_total_budgets() must return float regardless of DB backend."""

    def test_returns_float_when_no_plans(self, db_session):
        from app.plans.routes import _total_budgets
        result = _total_budgets(db_session)
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"
        assert result == 0.0

    def test_returns_float_with_multiple_plans(self, db_session):
        from app.plans.routes import _total_budgets
        make_plan(db_session, name="Plan A", budget=1000.0)
        make_plan(db_session, name="Plan B", budget=2500.0)
        result = _total_budgets(db_session)
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"
        assert result == 3500.0
```

### Why These Tests Still Run on SQLite

These `isinstance` tests pass on SQLite with or without the `float()` cast in source code — because SQLite already returns `float`. They are not behavior-divergence tests. Their purpose is:

1. **Document the invariant**: downstream code requires `float`, not `Decimal`
2. **Guard against regression**: if someone removes `float()` thinking it's redundant, the error message explains why it isn't
3. **Make the CI/production asymmetry visible at the assertion**: the docstring and message live where the invariant is checked, not buried in a comment in source code

## Prevention

### The isinstance Pattern for Numeric Aggregates

Add `isinstance` checks whenever testing `func.sum()`, `func.avg()`, or `func.coalesce()` over Numeric columns:

```python
result = function_returning_float_from_db()

# isinstance FIRST — because value equality passes silently even when type is wrong
assert isinstance(result, float), (
    "Must be float, not Decimal — Decimal + float arithmetic raises TypeError "
    "in production with PostgreSQL even though Decimal('5.0') == 5.0 passes silently"
)
assert result == expected_value
```

The `isinstance` check must come first. If the type is wrong, the value check passes anyway — leading first surfaces the failure on the correct axis.

### The "Explain Your Assertion" Rule

The assertion message must explain the production failure mode, not restate the check:

```python
# Bad — restates the obvious, will be deleted as "redundant"
assert isinstance(result, float), "result should be float"

# Required — explains what breaks and why
assert isinstance(result, float), (
    "Must be float, not Decimal — Decimal + float arithmetic raises TypeError "
    "in production with PostgreSQL even though Decimal('5.0') == 5.0 passes silently"
)
```

An `isinstance` check alongside a passing value assertion looks redundant. Without an explanation, a future cleanup pass deletes it. The message is the guard against the guard being removed.

### The Boundary Rule: `-> float` Functions That Call `.scalar()`

Any function annotated `-> float` that calls `q.scalar()` on a numeric aggregate needs two things, inseparably:

| Where | What |
|---|---|
| Source code | `return float(q.scalar() or 0)` at the `.scalar()` call |
| Test | `assert isinstance(result, float)` with production failure message |

Adding the cast without the test: the next refactor silently removes the cast.
Adding the test without the cast: the test passes on SQLite, providing false confidence.

### Detection Query

Find test assertions that may need `isinstance` guards:

```bash
grep -rln "func\.\(sum\|avg\|coalesce\)" backend/tests/ \
  | xargs grep -n "assert.*== [0-9]" \
  | grep -v "isinstance"
```

Any hit is a candidate. Triage by checking whether the asserted value comes from a `.scalar()` call on a Numeric aggregate — if yes, add the guard.

### Where This Does NOT Apply

`isinstance` is NOT needed for:
- **String fields** — PostgreSQL and SQLite both return `str`
- **Boolean fields** — no numeric coercion
- **Integer counts** — `func.count()` returns `int` in both backends
- **Values already cast** — if the source already does `float(q.scalar())`, a value test is sufficient (though isinstance is still good documentation)

The risk is specifically **Numeric/Decimal aggregations** (`Numeric`, `DECIMAL`, `Float` with `asdecimal=True`) where the result flows into float arithmetic.

## Related Documentation

- [`database-issues/sqlalchemy-decimal-float-sqlite-postgres-mismatch.md`](../database-issues/sqlalchemy-decimal-float-sqlite-postgres-mismatch.md) — The companion doc: what caused the production crash, the `float()` fix, and the audit of all vulnerable ORM sites. Read this first for the full context.
- [`database-issues/sqlite-datetime-timezone-stripping.md`](../database-issues/sqlite-datetime-timezone-stripping.md) — The same structural pattern: SQLite silently strips `DateTime(timezone=True)` metadata, causing naive/aware datetime mismatches that are invisible in CI.

### Cross-Cutting Pattern

These three docs in `database-issues/` form a cluster: **the test environment (SQLite in-memory + StaticPool) silently accepts things that production PostgreSQL handles differently**. All three represent production-only failures that passed CI:

1. `func.sum()` returns `Decimal` vs `float`
2. `DateTime(timezone=True)` strips timezone metadata  
3. Supabase batch migration executes differently than SQLite DDL

The systemic fix is integration tests running against real PostgreSQL. Until then, `isinstance` assertions and `float()` casts are the per-site mitigations.
