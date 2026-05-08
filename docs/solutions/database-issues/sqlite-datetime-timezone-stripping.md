---
name: SQLite DateTime timezone stripping in test environment
description: SQLite in-memory database silently strips timezone metadata from DateTime columns, causing naive/aware datetime mismatch errors in constraint validation tests
type: database-issue
severity: medium
component: constraints, models, testing
tags: [sqlite, timezone, testing, asyncio, sqlalchemy]
date: 2026-05-07
status: resolved
---

# SQLite DateTime Timezone Stripping in Test Environment

## Problem

Portfolio constraint validation tests were failing with a cryptic timezone mismatch error:

```
TypeError: can't subtract offset-naive and offset-aware datetimes
```

This occurred in 6 out of 11 async constraint tests when attempting to calculate hours elapsed between decision timestamps.

## Root Cause

SQLite's in-memory database (used in tests via `StaticPool`) stores `DateTime(timezone=True)` columns as ISO 8601 strings, **discarding timezone metadata**. When retrieved, datetimes come back as naive (no timezone information). 

The test fixtures and production code both used timezone-aware datetimes (`datetime.now(timezone.utc)`), creating a type mismatch:

```python
# Test fixture creates aware datetime
last_decision_timestamp=datetime.now(timezone.utc)  # ✓ aware

# SQLite stores, then returns naive datetime
touch.last_decision_timestamp  # ✗ naive (timezone stripped)

# Constraint checker attempts subtraction
hours_elapsed = (decision_timestamp - touch.last_decision_timestamp).total_seconds() / 3600
# Python raises: can't subtract offset-naive and offset-aware
```

This only manifested in the test environment because:
- Tests use SQLite in-memory with `StaticPool` (no actual database)
- Production uses PostgreSQL which correctly preserves timezone metadata
- The mismatch didn't surface until constraints test suite exercised the full datetime arithmetic path

## Solution

**Match test fixtures to SQLite's actual behavior by using naive datetimes:**

### Before (failing)
```python
@pytest.fixture
def portfolio(db_session):
    touch = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=datetime.now(timezone.utc),  # ✗ aware
        last_action="BUY",
    )
    db_session.add(touch)
    db_session.commit()
```

### After (passing)
```python
@pytest.fixture
def portfolio(db_session):
    touch = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=datetime.now(),  # ✓ naive
        last_action="BUY",
    )
    db_session.add(touch)
    db_session.commit()
```

**Files affected:**
- `backend/tests/plans/test_constraints.py`: Replaced 6 instances of `datetime.now(timezone.utc)` with `datetime.now()`
- **Result:** All 11 constraint tests passing; ~0.25s execution time

## Why This Works

The constraint checker doesn't actually need timezone information—it calculates **elapsed time** (hours between two points), which is timezone-agnostic. Both datetimes being naive means the subtraction succeeds:

```python
# Both naive: subtraction works fine
naive_1 = datetime.now()
naive_2 = datetime.now() - timedelta(hours=24)
hours = (naive_1 - naive_2).total_seconds() / 3600  # ✓ works
```

## Production Implications

**No impact on production code.** PostgreSQL preserves timezone metadata correctly, so production code continues to use `datetime.now(timezone.utc)` without issue. The constraint checker receives timezone-aware datetimes in production and produces correct results.

## Prevention Strategies

### Immediate (2 minutes)
- Document this SQLite limitation in test conftest
- Add a comment explaining why constraint tests use naive datetimes

### Short-term (15 minutes)
- Audit other test fixtures for similar timezone mismatches (Trade, GuardrailsAudit, PortfolioSnapshot models all use DateTime columns)
- Create a helper function `utc_aware_to_naive()` for test setup to make the conversion explicit

### Medium-term (1 hour)
- Consider replacing `StaticPool` with SQLite on-disk for tests that require production-accurate datetime behavior
- Or, add a test flag to models that strips timezone on retrieval (simulating SQLite) for fixtures that need it

### Long-term (architectural)
- Separate "integration tests" (against real PostgreSQL) from "unit tests" (against SQLite in-memory)
- Unit tests use naive datetimes; integration tests verify timezone handling end-to-end
- This is the Rails convention and prevents timezone surprises

## Best Practices Going Forward

**Naive vs. Aware Datetimes:**

| Context | Pattern | Reason |
|---------|---------|--------|
| **Constraint tests** | Use `datetime.now()` (naive) | Matches SQLite test behavior |
| **Production datetime fields** | Use `datetime.now(timezone.utc)` (aware) | PostgreSQL preserves metadata |
| **Model fixtures in tests** | Use naive datetimes | Mirrors what SQLite returns |
| **Time arithmetic in tests** | Safe either way (as long as consistent) | No timezone info needed for elapsed time |

## Test Coverage

The constraint test suite validates this fix across 11 test cases:

```python
# Cooldown enforcement (2 tests)
test_constraint_check_cooldown_enforced()        # ✓ 24h < 48h threshold
test_constraint_check_cooldown_passes_after_window()  # ✓ 49h > 48h threshold

# Action alternation (2 tests)
test_constraint_check_no_repeat_action()         # ✓ Blocks BUY after BUY
test_constraint_check_allows_action_switch()     # ✓ Allows SELL after BUY

# Touch history CRUD (2 tests)
test_update_touch_history_creates_new_entry()    # ✓ Creates record
test_update_touch_history_updates_existing_entry()  # ✓ Updates record

# Plus 5 more: HOLD bypass, frequency cap enforcement, portfolio isolation
```

All 11 passing with naive datetime fixtures.

## Related Issues & Patterns

- **Similar fix applied:** [commit 2fff6d6](https://github.com/yourrepo/commits/2fff6d6) — earlier timezone issue in Trade model testing
- **Related models affected:** Trade (`timestamp`), GuardrailsAudit (`timestamp`), PortfolioSnapshot (`date` — uses `Date` type, no timezone complications)
- **Solution category:** See `/docs/solutions/database-issues/` for other SQLite-in-memory test patterns
- **Architecture reference:** CLAUDE.md, Testing section — documents that tests use StaticPool for performance

## Developer Guidance

If you add new constraint tests or other tests involving datetime fields:

1. **Check if field is `DateTime` or `Date`**
   - `DateTime`: Use naive datetimes in fixtures (`datetime.now()`)
   - `Date`: No timezone concern; use `date.today()`

2. **Verify the subtraction type**
   - If subtracting two datetimes: ensure both are same type (both naive or both aware)
   - If only storing/retrieving: type doesn't matter as long as you don't do arithmetic

3. **Test against real PostgreSQL if timezone handling is critical**
   - Unit tests with SQLite are fast but timezone-blind
   - Integration tests with actual PostgreSQL catch timezone bugs

4. **Document why your fixture uses naive/aware**
   - Add a comment explaining the choice
   - Helps future developers understand the pattern
