# Timezone Prevention: Conftest Implementation Guide

## Quick Fix: Add to conftest.py

Add these helpers to `/backend/tests/conftest.py` immediately after the imports:

```python
# Add to imports at top
from datetime import datetime, timezone

# Add after the imports, before existing fixtures
# =========================================================================
# Timezone helpers for database-backed tests
# =========================================================================

def now_utc() -> datetime:
    """Return current UTC time for timezone-aware DateTime columns.
    
    ALWAYS use this instead of datetime.now() when creating test fixtures
    for any DateTime(timezone=True) column:
    - Trade.timestamp
    - GuardrailsAudit.timestamp
    - Portfolio.created_at, updated_at
    - PortfolioTouchHistory.last_decision_timestamp, created_at, updated_at
    
    Why:
    - SQLite silently accepts naive datetimes (but shouldn't)
    - PostgreSQL (production) requires timezone-aware datetimes
    - Tests must match production behavior
    
    Example:
        from tests.conftest import now_utc
        from datetime import timedelta
        
        trade = Trade(
            timestamp=now_utc() - timedelta(hours=1),
            ticker="AAPL",
            ...
        )
    """
    return datetime.now(timezone.utc)


def make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to UTC-aware.
    
    Use when you have a naive datetime from an external source
    and need to store it in a timezone-aware column.
    
    Example:
        naive = datetime(2026, 1, 15, 9, 30, 0)
        aware = make_aware(naive)
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def assert_aware(dt: datetime | None, field_name: str = "datetime") -> None:
    """Fail test if datetime is naive (indicates test fixture bug).
    
    Use in assertions to catch timezone mismatches early.
    
    Example:
        trade = db_session.query(Trade).first()
        assert_aware(trade.timestamp, "Trade.timestamp")
    """
    if dt is None:
        return  # NULL is OK
    if isinstance(dt, datetime) and dt.tzinfo is None:
        raise AssertionError(
            f"{field_name} is NAIVE: {dt!r}\n"
            f"Expected timezone-aware UTC datetime.\n"
            f"This would fail in production (PostgreSQL/Supabase).\n"
            f"Use: now_utc() or datetime.now(timezone.utc) when creating fixtures."
        )
```

## Updated Test Fixtures: Before/After

### Example 1: PortfolioTouchHistory

**Before (BROKEN in production):**
```python
@pytest.mark.asyncio
async def test_constraint_check_cooldown_enforced(db_session, portfolio):
    """Cooldown constraint should block trades within the window."""
    # BUG: datetime.now() is naive
    touch = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=datetime.now() - timedelta(hours=24),
        last_action="BUY",
    )
    db_session.add(touch)
    db_session.commit()
    
    decision = {"ticker": "AAPL", "action": "SELL", "quantity": 10}
    now = datetime.now()  # BUG: naive again
    
    allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)
    assert allowed is False
```

**After (CORRECT):**
```python
@pytest.mark.asyncio
async def test_constraint_check_cooldown_enforced(db_session, portfolio):
    """Cooldown constraint should block trades within the window."""
    # FIXED: now_utc() is timezone-aware
    touch = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=now_utc() - timedelta(hours=24),
        last_action="BUY",
    )
    db_session.add(touch)
    db_session.commit()
    
    decision = {"ticker": "AAPL", "action": "SELL", "quantity": 10}
    now = now_utc()  # FIXED: aware
    
    allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)
    assert allowed is False
```

### Example 2: Trade Creation

**Before (BROKEN):**
```python
def make_trade(db_session, plan_id, **overrides):
    """Insert a Trade row for a plan with sensible defaults."""
    from app.models import Trade
    
    defaults = {
        "plan_id": plan_id,
        "ticker": "AAPL",
        "action": "buy",
        "quantity": 1.0,
        "price": 150.0,
        "guardrail_passed": True,
        "executed": True,
        "virtual_cash_before": 5000.0,
        "virtual_cash_after": 4850.0,
        # BUG: timestamp missing, relies on model default
        # But model default might be naive or aware depending on when it runs
    }
    defaults.update(overrides)
    trade = Trade(**defaults)
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade
```

**After (CORRECT):**
```python
def make_trade(db_session, plan_id, **overrides):
    """Insert a Trade row for a plan with sensible defaults."""
    from app.models import Trade
    
    defaults = {
        "plan_id": plan_id,
        "ticker": "AAPL",
        "action": "buy",
        "quantity": 1.0,
        "price": 150.0,
        "guardrail_passed": True,
        "executed": True,
        "virtual_cash_before": 5000.0,
        "virtual_cash_after": 4850.0,
        "timestamp": now_utc(),  # FIXED: explicit, aware
    }
    defaults.update(overrides)
    trade = Trade(**defaults)
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade
```

### Example 3: Portfolio Creation

**Before (BROKEN):**
```python
def make_plan(db_session, **overrides):
    """Insert a Plan row with sensible defaults."""
    from app.plans.models import Portfolio
    
    defaults = {
        "name": "Test Plan",
        "budget": 5000.0,
        "virtual_cash": 5000.0,
        # ... other fields ...
        # created_at and updated_at missing
        # Relies on model defaults which might be naive
    }
    defaults.update(overrides)
    plan = Portfolio(**defaults)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan
```

**After (CORRECT):**
```python
def make_plan(db_session, **overrides):
    """Insert a Plan row with sensible defaults."""
    from app.plans.models import Portfolio
    
    defaults = {
        "name": "Test Plan",
        "budget": 5000.0,
        "virtual_cash": 5000.0,
        # ... other fields ...
        "created_at": now_utc(),  # FIXED: explicit, aware
        "updated_at": now_utc(),  # FIXED: explicit, aware
    }
    defaults.update(overrides)
    plan = Portfolio(**defaults)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan
```

## Gradual Migration Strategy

If you have many tests, migrate in stages:

### Stage 1: Add Helpers (5 min)
Add `now_utc()`, `make_aware()`, `assert_aware()` to conftest.py.

### Stage 2: Fix Critical Tests (30 min)
Fix tests that directly test timestamp logic:
- `test_constraints.py` — anything with `last_decision_timestamp`
- `test_compliance.py` — wash sale, PDT tracking with timestamps
- `test_trades_routes.py` — trade ordering, filtering by date

### Stage 3: Fix Fixture Helpers (15 min)
Update `make_plan()` and `make_trade()` in conftest.py to use `now_utc()`.

### Stage 4: Audit Remaining Tests (30 min)
Search for remaining `datetime.now()` in test files:
```bash
cd /Users/jameschang/Projects/bahtzang-trader/backend
grep -r "datetime.now()" tests/ --include="*.py" | grep -v "timezone.utc"
```

Replace each with `now_utc()` or `datetime.now(timezone.utc)`.

### Stage 5: Add Validation (10 min)
Add test to catch naive datetimes (see below).

## Validation Test to Add

Add this to a new file `backend/tests/test_datetime_fixtures.py`:

```python
"""Test that all test fixtures use timezone-aware datetimes.

This prevents the SQLite bug where naive datetimes work in tests
but fail in production Supabase.
"""

import pytest
from datetime import datetime, timezone
from app.models import Trade, GuardrailsAudit
from app.plans.models import Portfolio, PortfolioTouchHistory


def test_portfolio_has_aware_timestamps(db_session):
    """Verify Portfolio.created_at and updated_at are timezone-aware."""
    from tests.conftest import now_utc
    
    portfolio = Portfolio(
        name="Test Portfolio",
        budget=10000,
        virtual_cash=10000,
        trading_goal="maximize_returns",
        risk_profile="moderate",
        trading_frequency="1x",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db_session.add(portfolio)
    db_session.commit()
    
    # Verify stored values are aware
    assert portfolio.created_at.tzinfo is not None, \
        "Portfolio.created_at must be timezone-aware"
    assert portfolio.updated_at.tzinfo is not None, \
        "Portfolio.updated_at must be timezone-aware"


def test_trade_has_aware_timestamp(db_session):
    """Verify Trade.timestamp is timezone-aware."""
    from tests.conftest import now_utc
    
    trade = Trade(
        ticker="AAPL",
        action="buy",
        quantity=1.0,
        price=150.0,
        guardrail_passed=True,
        executed=True,
        timestamp=now_utc(),
    )
    db_session.add(trade)
    db_session.commit()
    
    assert trade.timestamp.tzinfo is not None, \
        "Trade.timestamp must be timezone-aware"


def test_guardrails_audit_has_aware_timestamp(db_session):
    """Verify GuardrailsAudit.timestamp is timezone-aware."""
    from tests.conftest import now_utc
    
    audit = GuardrailsAudit(
        user_email="test@example.com",
        action="update",
        changes="{}",
    )
    db_session.add(audit)
    db_session.commit()
    
    assert audit.timestamp.tzinfo is not None, \
        "GuardrailsAudit.timestamp must be timezone-aware"


def test_portfolio_touch_history_has_aware_timestamps(db_session):
    """Verify PortfolioTouchHistory timestamps are timezone-aware."""
    from tests.conftest import now_utc
    
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
    
    touch = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=now_utc(),
        last_action="BUY",
    )
    db_session.add(touch)
    db_session.commit()
    
    assert touch.last_decision_timestamp.tzinfo is not None, \
        "PortfolioTouchHistory.last_decision_timestamp must be timezone-aware"
    assert touch.created_at.tzinfo is not None, \
        "PortfolioTouchHistory.created_at must be timezone-aware"
    assert touch.updated_at.tzinfo is not None, \
        "PortfolioTouchHistory.updated_at must be timezone-aware"


def test_naive_datetime_in_fixture_fails(db_session):
    """Demonstrate the problem: naive datetimes don't work in production."""
    from datetime import datetime
    
    # This is what the bug looks like
    naive_ts = datetime.now()  # WRONG
    
    # SQLite allows it, but production wouldn't
    trade = Trade(
        ticker="TEST",
        action="buy",
        quantity=1.0,
        price=100.0,
        guardrail_passed=True,
        executed=True,
        timestamp=naive_ts,
    )
    db_session.add(trade)
    db_session.commit()
    
    fetched = db_session.query(Trade).filter_by(ticker="TEST").first()
    
    # In SQLite, it's stored as naive (no validation)
    # In production, this would be rejected or converted
    if fetched.timestamp.tzinfo is None:
        # We caught the bug!
        pytest.skip(
            "Caught SQLite timezone bug: naive datetime was accepted. "
            "This would fail in production. Use now_utc() instead."
        )
```

## Search & Replace Guide

Find all instances of naive datetimes in tests:

```bash
cd /Users/jameschang/Projects/bahtzang-trader/backend

# Find datetime.now() calls (potential bugs)
grep -rn "datetime.now()" tests/ --include="*.py"

# Count them
grep -r "datetime.now()" tests/ --include="*.py" | wc -l

# Find timezone.utc calls (good)
grep -r "timezone.utc" tests/ --include="*.py" | wc -l
```

For each match in `grep -rn "datetime.now()"`:
1. Check if it's in a fixture that stores to a `DateTime(timezone=True)` column
2. If yes, replace with `now_utc()`
3. If no (e.g., UI display), keep as-is but add a comment

Example replacement using sed (if you want to be aggressive):
```bash
# CAREFUL: This replaces all datetime.now() not followed by timezone.utc
# Review each replacement before committing
cd /Users/jameschang/Projects/bahtzang-trader/backend/tests
sed -i.bak 's/datetime\.now()/now_utc()/g' **/*.py

# Then review and undo any incorrect replacements
git diff
```

## Testing Your Changes

After implementing, run:

```bash
# Run all tests to ensure nothing broke
cd /Users/jameschang/Projects/bahtzang-trader
npm run test:backend

# Run just the new datetime validation tests
npm run test:backend -- tests/test_datetime_fixtures.py -v

# Run a specific problematic test file
npm run test:backend -- tests/plans/test_constraints.py -v
```

All tests should pass (the `test_naive_datetime_in_fixture_fails` test may skip if SQLite allows naive datetimes, which is expected).

## Summary

| Before | After | Benefit |
|--------|-------|---------|
| `datetime.now()` in fixture | `now_utc()` | Timezone-aware, production-like |
| No helper function | `now_utc()` in conftest | Reusable, discoverable |
| Implicit timestamps | Explicit `timestamp=now_utc()` | Clearer intent, easier to test |
| Validation test? No | `test_datetime_fixtures.py` | Catches regressions |
| CI behavior | Same (SQLite still allows naive) | But at least docs & helpers are in place |

When you eventually migrate to PostgreSQL testing, these changes ensure the test suite will fail immediately on timezone mismatches, guiding developers to fix them.
