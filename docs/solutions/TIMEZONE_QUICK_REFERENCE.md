---
id: DOC-031
type: solution
status: active
phase: null
owner: james
tags: [testing, backend]
links: []
updated: 2026-07-22
---

# Timezone Testing: Quick Reference

## The One-Sentence Problem

Tests use naive datetimes (`datetime.now()`) which SQLite accepts, but production uses Supabase which requires timezone-aware UTC datetimes (`datetime.now(timezone.utc)`).

## Two-Minute Fix

### 1. Add to conftest.py:
```python
from datetime import datetime, timezone

def now_utc() -> datetime:
    """Return current UTC time for timezone-aware DateTime columns."""
    return datetime.now(timezone.utc)
```

### 2. In test fixtures, replace:
```python
# WRONG
timestamp=datetime.now()

# CORRECT
timestamp=now_utc()
```

### 3. Run tests:
```bash
npm run test:backend
```

## When to Use What

| Situation | Code | Why |
|-----------|------|-----|
| Trade timestamp | `now_utc()` | Column is `DateTime(timezone=True)` |
| Portfolio created_at | `now_utc()` | Column is `DateTime(timezone=True)` |
| Touch history timestamp | `now_utc()` | Column is `DateTime(timezone=True)` |
| Audit log timestamp | `now_utc()` | Column is `DateTime(timezone=True)` |
| Portfolio snapshot date | `date.today()` | Column is `Date`, not DateTime |
| UI display (local time) | `datetime.now()` | Not stored, just display |

## Imports Needed

```python
from datetime import datetime, timezone, timedelta
from tests.conftest import now_utc  # After adding helper
```

## Common Patterns

### Pattern 1: Create record with current time
```python
# Before (WRONG)
trade = Trade(
    ticker="AAPL",
    timestamp=datetime.now(),  # ❌ naive
    ...
)

# After (CORRECT)
trade = Trade(
    ticker="AAPL",
    timestamp=now_utc(),  # ✓ aware
    ...
)
```

### Pattern 2: Create record with offset time
```python
# Before (WRONG)
touch = PortfolioTouchHistory(
    last_decision_timestamp=datetime.now() - timedelta(hours=24),  # ❌ naive
    ...
)

# After (CORRECT)
touch = PortfolioTouchHistory(
    last_decision_timestamp=now_utc() - timedelta(hours=24),  # ✓ aware
    ...
)
```

### Pattern 3: Compare timestamps in test
```python
# Before (WRONG)
now = datetime.now()  # ❌ naive
ts = db_session.query(Trade).first().timestamp  # ✓ aware from DB
if ts > now:  # ❌ Can't compare naive and aware
    ...

# After (CORRECT)
now = now_utc()  # ✓ aware
ts = db_session.query(Trade).first().timestamp  # ✓ aware from DB
if ts > now:  # ✓ Both aware, comparison works
    ...
```

### Pattern 4: Fixed reference time
```python
# Before (WRONG)
ref_time = datetime(2026, 1, 15, 9, 30, 0)  # ❌ naive

# After (CORRECT)
ref_time = datetime(2026, 1, 15, 9, 30, 0, tzinfo=timezone.utc)  # ✓ aware
# OR
ref_time = datetime.fromisoformat("2026-01-15T09:30:00+00:00")  # ✓ aware
```

## Red Flags

Watch for these warning signs:

```python
# ❌ WRONG: Creating without timezone
last_ts = datetime.now()

# ❌ WRONG: Comparing aware and naive
if db_record.timestamp > datetime.now():

# ❌ WRONG: Using local time for database
created_at = datetime.fromtimestamp(time.time())

# ❌ WRONG: No offset in fixed time
base_time = datetime(2026, 1, 1, 0, 0, 0)

# ✓ CORRECT: Always aware UTC
now = datetime.now(timezone.utc)
```

## File Locations

| Document | Purpose |
|----------|---------|
| `docs/solutions/TIMEZONE_TESTING_GUIDE.md` | **Full guide** — problem explanation, best practices, all test patterns |
| `docs/solutions/TIMEZONE_CONFTEST_IMPLEMENTATION.md` | **Implementation** — exact code to add, before/after examples, migration stages |
| `docs/solutions/TIMEZONE_QUICK_REFERENCE.md` | **This file** — quick lookup, checklists, patterns |

## Checklist: Before Committing Tests

- [ ] All `DateTime(timezone=True)` columns use `now_utc()` or `datetime.now(timezone.utc)`
- [ ] No `datetime.now()` in test fixtures that touch the database
- [ ] No mixing of naive and aware in comparisons
- [ ] Fixed times include `tzinfo=timezone.utc`
- [ ] Imports include `from datetime import timezone`
- [ ] Tests pass: `npm run test:backend`

## Implementation Checklist

- [ ] Add `now_utc()` to `backend/tests/conftest.py`
- [ ] Add `make_aware()` to conftest (optional, nice-to-have)
- [ ] Add `assert_aware()` to conftest (optional, nice-to-have)
- [ ] Update `make_plan()` in conftest to use `now_utc()`
- [ ] Update `make_trade()` in conftest to use `now_utc()`
- [ ] Search `grep -r "datetime.now()" backend/tests/` and fix matches
- [ ] Add `test_datetime_fixtures.py` validation test
- [ ] Run full test suite: `npm run test:backend`
- [ ] Update CLAUDE.md with reference to timezone guide

## Model Fields That Need Aware Datetimes

| Model | Fields | Column Type |
|-------|--------|-------------|
| `Trade` | `timestamp` | `DateTime(timezone=True)` |
| `GuardrailsAudit` | `timestamp` | `DateTime(timezone=True)` |
| `Portfolio` | `created_at`, `updated_at` | `DateTime(timezone=True)` |
| `PortfolioTouchHistory` | `last_decision_timestamp`, `created_at`, `updated_at` | `DateTime(timezone=True)` |
| `PortfolioStrategyAudit` | `timestamp` | `DateTime(timezone=True)` |
| `BacktestResult` | `created_at` | `DateTime(timezone=True)` |
| `EarningsEvent` | (none with tz=True) | — |
| `PortfolioSnapshot` | (none with tz=True, uses `Date`) | `Date` |

For **Date columns**, use `date.today()` not `datetime.now()`.

## Why This Matters in 30 Seconds

1. **Supabase (production):** Uses PostgreSQL, which has a timezone-aware datetime type. Every stored timestamp includes a UTC offset. Comparisons and filters work correctly.

2. **SQLite (tests):** Has no datetime type. Stores everything as text. When you pass a naive datetime, it gets stored without an offset. When you read it back, Python reads it as naive again. No error thrown.

3. **The Bug:** Test creates naive datetime → SQLite stores it as naive string → Query returns naive → Comparison succeeds in test but would fail in production. Silent bug.

4. **The Fix:** Always use `datetime.now(timezone.utc)` in test fixtures. If tests ever migrate to PostgreSQL, they'll fail loudly at naive datetimes, and developers will fix them. Until then, code looks production-ready.

## Example: Before and After

### Test File: before
```python
# tests/plans/test_constraints.py
from datetime import datetime, timedelta

async def test_cooldown_enforced(db_session, portfolio):
    touch = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=datetime.now() - timedelta(hours=24),  # ❌ NAIVE
        last_action="BUY",
    )
    db_session.add(touch)
    db_session.commit()
    
    now = datetime.now()  # ❌ NAIVE
    allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)
    assert allowed is False
```

### Test File: after
```python
# tests/plans/test_constraints.py
from datetime import datetime, timezone, timedelta
from tests.conftest import now_utc

async def test_cooldown_enforced(db_session, portfolio):
    touch = PortfolioTouchHistory(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        last_decision_timestamp=now_utc() - timedelta(hours=24),  # ✓ AWARE
        last_action="BUY",
    )
    db_session.add(touch)
    db_session.commit()
    
    now = now_utc()  # ✓ AWARE
    allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)
    assert allowed is False
```

## Time Estimate

| Task | Time | Impact |
|------|------|--------|
| Add `now_utc()` to conftest | 2 min | High (enables all fixes) |
| Fix `make_plan()` and `make_trade()` | 5 min | High (covers most tests) |
| Audit remaining `datetime.now()` | 15 min | Medium (catches stragglers) |
| Add validation test | 5 min | Medium (prevents regression) |
| Run full test suite | 5 min | High (verify no breakage) |
| **Total** | **~30 min** | **Prevents silent production bugs** |

## Next Steps

1. Read `TIMEZONE_TESTING_GUIDE.md` for full context (10 min read)
2. Follow `TIMEZONE_CONFTEST_IMPLEMENTATION.md` to add helpers (15 min implementation)
3. Use this quick reference sheet for patterns (ongoing)
4. Link developers to `TIMEZONE_TESTING_GUIDE.md` when they ask about datetimes

## One-Liner for Developers

**"When storing to a database: use `datetime.now(timezone.utc)` not `datetime.now()`. We test against SQLite which doesn't validate timezones, but production uses Supabase which does."**
