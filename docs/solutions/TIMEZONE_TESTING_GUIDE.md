---
id: DOC-032
type: solution
status: active
phase: null
owner: james
tags: [testing, backend]
links: []
updated: 2026-07-22
---

# Timezone Testing Guide

## The Problem

The bahtzang-trader codebase uses PostgreSQL (Supabase in production) with timezone-aware datetime columns (`DateTime(timezone=True)` in SQLAlchemy), but tests run against SQLite, which has a critical mismatch:

- **Production (Supabase):** Stores and compares timezone-aware UTC datetimes
- **Tests (SQLite):** Naively handles datetimes — doesn't enforce timezone awareness
- **The Bug:** Tests create records with naive `datetime.now()` while columns expect `datetime.now(timezone.utc)` (aware)

When a test stores a naive datetime in a timezone-aware column:
- SQLite silently accepts it (no validation)
- The value is stored as-is: `2026-05-07T23:01:20` (no UTC offset)
- Comparisons fail because naive ≠ aware in Python

Production never hits this — Supabase rejects the insert or forces conversion. **Tests pass in CI but the code would fail in production.**

## The Root Cause

### Naive vs Aware Datetimes

```python
from datetime import datetime, timezone

# NAIVE — no timezone info (WRONG for test fixtures)
naive = datetime.now()
# Result: 2026-05-07T23:01:20.058318
# Problem: When stored in timezone-aware column, loses context

# AWARE — explicit UTC (CORRECT for test fixtures)
aware = datetime.now(timezone.utc)
# Result: 2026-05-08T06:01:20.058330+00:00
# Benefit: Explicit UTC; survives round-trip through any database
```

### Why SQLite Doesn't Catch This

SQLite has no native datetime type — it stores everything as TEXT or UNIX timestamps. When you write:

```python
last_decision_timestamp=datetime.now()  # naive
```

SQLite converts to string: `"2026-05-07T23:01:20.058318"` and stores it. No validation.

When you read it back, SQLAlchemy calls `datetime.fromisoformat()`, which:
- Recognizes `"2026-05-07T23:01:20.058318"` as naive
- Returns a naive datetime object
- Returns successfully because Python accepts it

PostgreSQL (Supabase), by contrast:
- Has a native `TIMESTAMP WITH TIME ZONE` type
- Requires timezone-aware input or explicit conversion
- Rejects naive datetimes (or auto-converts, depending on settings)

## Prevention Strategies

### 1. Use Timezone-Aware Fixtures (Immediate)

Replace all naive `datetime.now()` in test fixtures with `datetime.now(timezone.utc)`:

```python
# Before (WRONG)
touch = PortfolioTouchHistory(
    portfolio_id=portfolio.id,
    ticker="AAPL",
    last_decision_timestamp=datetime.now() - timedelta(hours=24),
    last_action="BUY",
)

# After (CORRECT)
from datetime import datetime, timezone
touch = PortfolioTouchHistory(
    portfolio_id=portfolio.id,
    ticker="AAPL",
    last_decision_timestamp=datetime.now(timezone.utc) - timedelta(hours=24),
    last_action="BUY",
)
```

### 2. Add a Conftest Helper (Medium)

Create a reusable helper in `tests/conftest.py`:

```python
from datetime import datetime, timezone

def now_utc() -> datetime:
    """Return current time in UTC (for timezone-aware columns).
    
    Use this instead of datetime.now() in test fixtures for any
    DateTime(timezone=True) columns.
    """
    return datetime.now(timezone.utc)
```

Usage:

```python
last_decision_timestamp=now_utc() - timedelta(hours=24),
```

### 3. Add Fixture Validation (Medium-High)

Add a conftest hook that validates all datetime fixtures are aware:

```python
import pytest
from datetime import datetime, timezone

@pytest.fixture(autouse=True)
def validate_fixture_timezones(request):
    """Catch naive datetimes in test fixtures before they hit the DB."""
    # This runs after every test
    # You could inspect request.getfixturevalue() results and warn
    yield
    # Post-test validation can check that all created objects have aware datetimes
```

### 4. Detect Mismatches in Queries (High)

Add a helper to detect when test data doesn't match production behavior:

```python
def assert_timestamp_aware(ts: datetime, field_name: str = "timestamp"):
    """Fail fast if timestamp is naive (wouldn't work in production)."""
    if ts.tzinfo is None:
        pytest.fail(
            f"{field_name} is naive: {ts!r}. "
            f"Use datetime.now(timezone.utc) instead of datetime.now()."
        )
```

## Best Practices for This Codebase

### When to Use Naive vs Aware

| Scenario | Use | Example |
|----------|-----|---------|
| **Storing in `DateTime(timezone=True)` column** | `datetime.now(timezone.utc)` | Trade timestamps, audit logs |
| **Storing in `Date` column** | `datetime.now().date()` or `date.today()` | Portfolio snapshots (date only) |
| **Local time (UI display only)** | `datetime.now()` (naive) | Frontend: "Last updated: 3:45 PM" |
| **Fixed reference time in tests** | `datetime.fromisoformat()` with explicit TZ | `datetime.fromisoformat("2026-01-15T09:30:00+00:00")` |
| **Comparing timestamps** | Always aware, always UTC | Production code: `datetime.now(timezone.utc)` |

### Guidelines for Test Fixtures Involving DateTime Fields

1. **Always use timezone-aware UTC for any `DateTime(timezone=True)` column:**
   ```python
   timestamp=datetime.now(timezone.utc)
   created_at=datetime.now(timezone.utc)
   ```

2. **Use the helper when available:**
   ```python
   from tests.conftest import now_utc
   timestamp=now_utc() - timedelta(hours=24)
   ```

3. **Never mix naive and aware in the same test:**
   ```python
   # WRONG
   stored_ts = now_utc()
   check_ts = datetime.now()  # naive
   assert stored_ts > check_ts  # Will fail: can't compare aware & naive
   
   # CORRECT
   stored_ts = now_utc()
   check_ts = now_utc()
   assert stored_ts > check_ts
   ```

4. **When constructing fixed times, include UTC offset:**
   ```python
   # WRONG
   base = datetime(2026, 1, 15, 9, 30, 0)
   
   # CORRECT
   base = datetime(2026, 1, 15, 9, 30, 0, tzinfo=timezone.utc)
   # Or use fromisoformat
   base = datetime.fromisoformat("2026-01-15T09:30:00+00:00")
   ```

### How to Structure Tests That Query Timestamps

Pattern: **Collect times at test-start, use for assertions, always UTC:**

```python
@pytest.mark.asyncio
async def test_trades_ordered_by_timestamp(db_session):
    """Verify trades are returned in descending timestamp order."""
    from datetime import datetime, timezone, timedelta
    
    # 1. Get a reference time (UTC)
    now = datetime.now(timezone.utc)
    
    # 2. Create test records with offsets from that time
    trade1 = Trade(timestamp=now - timedelta(hours=2))
    trade2 = Trade(timestamp=now - timedelta(hours=1))
    trade3 = Trade(timestamp=now)
    
    # 3. Query and assert
    trades = db_session.query(Trade).order_by(Trade.timestamp.desc()).all()
    assert [t.id for t in trades] == [trade3.id, trade2.id, trade1.id]
    
    # 4. Comparisons work because all datetimes are aware
    assert trades[0].timestamp > trades[1].timestamp
```

## Test Case Suggestions

### 1. Test Case That Catches Timezone Mismatch

Add this to `tests/test_datetime_fixtures.py`:

```python
"""Test that all DateTime(timezone=True) fixtures are timezone-aware.

This test catches the subtle SQLite bug where naive datetimes
pass in tests but fail in production.
"""

import pytest
from datetime import datetime, timezone
from app.models import Trade, GuardrailsAudit
from app.plans.models import PortfolioTouchHistory, Portfolio


def test_all_datetime_fixtures_are_timezone_aware(db_session):
    """Verify that test fixtures use aware datetimes for timezone=True columns."""
    
    # Create fixtures
    portfolio = Portfolio(
        name="Test",
        budget=1000,
        virtual_cash=1000,
        trading_goal="maximize_returns",
        risk_profile="moderate",
        trading_frequency="1x",
    )
    db_session.add(portfolio)
    db_session.commit()
    
    trade = Trade(
        ticker="AAPL",
        action="buy",
        quantity=1.0,
        price=150.0,
        guardrail_passed=True,
        executed=True,
    )
    db_session.add(trade)
    db_session.commit()
    
    touch_history = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=datetime.now(timezone.utc),
        last_action="BUY",
    )
    db_session.add(touch_history)
    db_session.commit()
    
    audit = GuardrailsAudit(
        user_email="test@example.com",
        action="update",
        changes="{}",
    )
    db_session.add(audit)
    db_session.commit()
    
    # Assert all datetime fields are timezone-aware
    assert portfolio.created_at.tzinfo is not None, \
        "Portfolio.created_at must be timezone-aware"
    assert trade.timestamp.tzinfo is not None, \
        "Trade.timestamp must be timezone-aware"
    assert touch_history.last_decision_timestamp.tzinfo is not None, \
        "PortfolioTouchHistory.last_decision_timestamp must be timezone-aware"
    assert audit.timestamp.tzinfo is not None, \
        "GuardrailsAudit.timestamp must be timezone-aware"


def test_naive_datetime_would_fail_in_production(db_session):
    """Demonstrate that naive datetimes work in SQLite but fail conceptually."""
    from datetime import datetime
    
    # This is what the bug looks like — naively creating a timestamp
    naive_ts = datetime.now()
    
    # SQLite lets you store it (no validation)
    trade = Trade(
        ticker="TEST",
        action="buy",
        quantity=1.0,
        price=100.0,
        guardrail_passed=True,
        executed=True,
        timestamp=naive_ts,  # WRONG, but SQLite allows it
    )
    db_session.add(trade)
    db_session.commit()
    
    # Read it back — it's still naive
    fetched = db_session.query(Trade).filter_by(ticker="TEST").first()
    
    # This would fail in production where datetimes are always aware
    # Use this to document the difference
    assert fetched.timestamp.tzinfo is None, \
        "SQLite allowed naive datetime (bug: wouldn't happen in production)"
    
    # The fix
    aware_ts = datetime.now(timezone.utc)
    assert aware_ts.tzinfo is not None
```

### 2. Validation to Add to conftest.py

```python
"""Catch timezone mismatches in test setup."""

from datetime import datetime, timezone
import pytest


def now_utc() -> datetime:
    """Return current UTC time for timezone-aware DateTime columns."""
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _check_datetime_awareness(request):
    """
    Auto-validate that any Trade, Portfolio, PortfolioTouchHistory, etc.
    created in the test have timezone-aware timestamps.
    
    This prevents silent bugs where naive datetimes work in SQLite
    but would fail in production Supabase.
    """
    # Pre-test: no validation needed
    yield
    
    # Post-test: you could inspect created objects here
    # For now, this is a placeholder for future enhancement
    # (would require storing created objects and validating their datetime fields)
    pass
```

### 3. Checks for Fixture Timezone Correctness

```python
"""Helper to verify fixtures are correctly timezone-aware."""

from datetime import datetime, timezone
import pytest


def assert_timestamp_aware(obj, field_name="timestamp"):
    """Fail fast if a datetime field is naive (would break in production)."""
    ts = getattr(obj, field_name)
    if ts is None:
        return  # NULL is OK
    
    if isinstance(ts, datetime) and ts.tzinfo is None:
        pytest.fail(
            f"{type(obj).__name__}.{field_name} is NAIVE: {ts!r}\n"
            f"Expected timezone-aware UTC datetime.\n"
            f"Use: datetime.now(timezone.utc) instead of datetime.now()"
        )


def assert_all_timestamps_aware(objects, datetime_fields):
    """
    Check that all datetime fields in a list of objects are timezone-aware.
    
    Usage:
        trades = db_session.query(Trade).all()
        assert_all_timestamps_aware(trades, ["timestamp"])
    """
    for obj in objects:
        for field_name in datetime_fields:
            assert_timestamp_aware(obj, field_name)
```

## Developer Guidance

### Rule of Thumb

```
If the column is DateTime(timezone=True) → Always use datetime.now(timezone.utc)
If the column is Date → Use datetime.now().date() or date.today()
If it's production code → Always use datetime.now(timezone.utc) for comparisons
If it's test code → Import now_utc() from conftest or use timezone.utc explicitly
```

### Why SQLite Behaves This Way

SQLite doesn't have a native datetime type — it stores datetimes as:
- TEXT (ISO 8601 string): `"2026-05-08T06:01:20.058330+00:00"`
- INTEGER (Unix timestamp): `1714900880`
- REAL (Julian day number): `2461123.75`

When you pass a naive datetime to a TEXT-based column, SQLite's Python driver (`sqlite3`) calls `.isoformat()`, which produces a string **without timezone offset**:
```
naive.isoformat()  # "2026-05-07T23:01:20.058318" (no +00:00)
aware.isoformat()  # "2026-05-08T06:01:20.058330+00:00" (has +00:00)
```

On read, SQLAlchemy's `DateTime` type calls `datetime.fromisoformat(string)`. If the string has no offset, `fromisoformat()` returns naive. SQLAlchemy then wraps it (still naive) because it trusts the driver.

**PostgreSQL/Supabase:** Has a true `TIMESTAMP WITH TIME ZONE` type. It validates that inputs are aware or auto-converts, and stores the offset in the database. No ambiguity.

### How It Relates to Production (Supabase)

In production:
1. Code uses `datetime.now(timezone.utc)` (correct)
2. Supabase's PostgreSQL driver sends aware datetime
3. PostgreSQL validates it's aware, stores with offset
4. Query results are always timezone-aware

In tests (SQLite):
1. Test fixture uses naive `datetime.now()` (bug)
2. SQLite accepts it, stores as `"2026-05-07T23:01:20.058318"`
3. Query result is naive (no offset in the string)
4. **Comparisons fail:** naive vs aware mismatch
5. Bug goes undetected until production

### Migration Path: SQLite → PostgreSQL Testing

When you switch test DB from SQLite to PostgreSQL:

1. **Run full test suite** — Tests using naive datetimes will now **fail** (good!)
2. **Fix each failure:** Replace `datetime.now()` with `datetime.now(timezone.utc)`
3. **Add conftest validation** — Catch any new naive datetimes
4. **Update developer docs** — Link to this guide

Example migration output:
```
FAILED test_constraints.py::test_cooldown_enforced
   Fail: "column 'last_decision_timestamp' does not accept naive datetimes"
   Fix: Use datetime.now(timezone.utc) instead of datetime.now()
```

## When This Matters vs When It Doesn't

### ALWAYS Matters

- **Any `DateTime(timezone=True)` column** in a model → Use `datetime.now(timezone.utc)`
- **Tests for guardrails, compliance, or trading logic** that compare timestamps
- **Any feature that queries by date range** (e.g., "trades in the last 24 hours")
- **Batch operations** that touch multiple records with timestamps

### Often Matters

- **Portfolio snapshots** (date, not datetime) — Use `.date()` to extract; naive is OK for Date columns
- **UI display times** — Local time (naive) is fine for display; convert at render time

### Rarely Matters

- **Static config values** with no temporal logic
- **Enum fields** or string fields
- **Tests that don't query by timestamp** (e.g., "does this field exist?")

## Warning Signs: Timezone Mismatch

Watch for these patterns in test failures:

### 1. Comparison Fails with `TypeError`
```
TypeError: '>' not supported between instances of 'datetime.datetime' and 'datetime.datetime'
```
**Cause:** Comparing aware and naive datetimes.
**Fix:** Ensure both sides use `timezone.utc`.

### 2. Query Returns Unexpected Results
```python
# Test creates: datetime.now() - timedelta(hours=24) (naive)
# Query searches: WHERE timestamp > datetime.now(timezone.utc) (aware)
# Result: No matches (comparing incompatible types)
```
**Cause:** Mixing naive and aware in filters.
**Fix:** Use aware in fixtures, aware in queries.

### 3. Assertion Passes in SQLite but Fails in PostgreSQL
```python
# SQLite: passes (naive stored and retrieved as naive)
# PostgreSQL: fails (naive rejected on insert or converted inconsistently)
```
**Cause:** Test relies on SQLite's lax timezone handling.
**Fix:** Use `datetime.now(timezone.utc)` in fixtures.

### 4. CI Passes, Production Fails
```
The test suite passes, but the live trading bot crashes on a timestamp comparison.
```
**Cause:** Tests use SQLite; production uses Supabase.
**Fix:** Run test suite against PostgreSQL or enforce timezone-aware fixtures.

## Summary Checklist

- [ ] All `DateTime(timezone=True)` columns use `datetime.now(timezone.utc)` in fixtures
- [ ] Conftest has a `now_utc()` helper for reusability
- [ ] Tests that query by timestamp use aware datetimes in WHERE clauses
- [ ] No mixing of naive and aware datetimes in the same test
- [ ] Fixed reference times use `tzinfo=timezone.utc` parameter
- [ ] Date-only columns use `.date()` method, not DateTime
- [ ] Developers know to import `timezone` from `datetime` module
- [ ] Developer docs link to this guide
- [ ] CI includes a check for timezone-aware fixtures (optional, nice-to-have)
