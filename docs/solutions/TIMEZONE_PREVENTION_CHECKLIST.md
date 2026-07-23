---
id: DOC-030
type: solution
status: active
phase: null
owner: james
tags: [testing, backend]
links: []
updated: 2026-07-22
---

# Timezone Prevention Strategy: Implementation Checklist

## Executive Summary

**Problem:** Tests use naive datetimes that SQLite accepts but Supabase PostgreSQL would reject. Silent bugs that don't surface until production.

**Solution:** Five-tier prevention strategy combining immediate fixes, developer guidance, automated validation, and infrastructure improvements.

**Impact:** 30-minute implementation that eliminates an entire class of timezone-related production bugs.

---

## Tier 1: Immediate Fixes (5-10 minutes)

### Action Item 1.1: Add Timezone Helper to conftest.py
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
Add this function to `/backend/tests/conftest.py` after imports:

```python
from datetime import datetime, timezone

def now_utc() -> datetime:
    """Return current UTC time for timezone-aware DateTime columns."""
    return datetime.now(timezone.utc)
```

**Why:** Makes the intent explicit. Developers see `now_utc()` and immediately know "this goes to the database."

**Time:** 2 minutes

**Verification:** 
```bash
grep "def now_utc" backend/tests/conftest.py
```

### Action Item 1.2: Fix Fixture Helpers
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
Update `make_plan()` and `make_trade()` in conftest.py:

```python
def make_plan(db_session, **overrides):
    from app.plans.models import Portfolio
    defaults = {
        ...
        "created_at": now_utc(),  # ADD THIS
        "updated_at": now_utc(),  # ADD THIS
    }
    # ... rest of function
```

```python
def make_trade(db_session, plan_id, **overrides):
    from app.models import Trade
    defaults = {
        ...
        "timestamp": now_utc(),  # ADD THIS
    }
    # ... rest of function
```

**Why:** These are the most-used fixtures. Fixing them fixes ~80% of tests automatically.

**Time:** 3 minutes

**Verification:** Run `npm run test:backend` and check no new failures

---

## Tier 2: Code Audit (15 minutes)

### Action Item 2.1: Find All Naive Datetimes in Tests
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
```bash
cd /Users/jameschang/Projects/bahtzang-trader/backend
grep -rn "datetime.now()" tests/ --include="*.py" | grep -v "timezone.utc"
```

**Expected output:** List of files and line numbers with naive `datetime.now()` calls

**Time:** 2 minutes (scan only)

**Document findings:** Save the output to a file:
```bash
grep -rn "datetime.now()" tests/ --include="*.py" | grep -v "timezone.utc" > /tmp/naive_datetimes.txt
wc -l /tmp/naive_datetimes.txt  # Count how many to fix
```

### Action Item 2.2: Categorize the Findings
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

For each file in the findings:
- **Category A (Fix immediately):** Used in database fixtures → Replace with `now_utc()`
- **Category B (Review):** Used in business logic → Check if it needs aware datetime
- **Category C (Keep):** UI display only, local time is fine → Add `# Local time for display` comment

**Time:** 5 minutes

### Action Item 2.3: Fix Category A
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

Go through each Category A file and replace `datetime.now()` with `now_utc()`.

Focus areas:
- `/tests/plans/test_constraints.py` — Trading timestamp logic
- `/tests/test_compliance.py` — PDT and wash sale with dates
- Any test file with `last_decision_timestamp`, `created_at`, `updated_at`, or `timestamp` assignments

**Time:** 8 minutes

**Verification:** Re-run the grep command — count should decrease significantly

---

## Tier 3: Validation Tests (10 minutes)

### Action Item 3.1: Create test_datetime_fixtures.py
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
Create `/backend/tests/test_datetime_fixtures.py` with this content:

```python
"""Test that all test fixtures use timezone-aware datetimes."""

import pytest
from datetime import datetime, timezone
from tests.conftest import now_utc
from app.models import Trade, GuardrailsAudit
from app.plans.models import Portfolio, PortfolioTouchHistory


def test_trade_timestamp_is_aware(db_session):
    """Trade.timestamp must be timezone-aware (DateTime(timezone=True))."""
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
        "Trade.timestamp must be timezone-aware for Supabase compatibility"


def test_portfolio_timestamps_are_aware(db_session):
    """Portfolio.created_at and updated_at must be timezone-aware."""
    portfolio = Portfolio(
        name="Test",
        budget=1000,
        virtual_cash=1000,
        trading_goal="maximize_returns",
        risk_profile="moderate",
        trading_frequency="1x",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db_session.add(portfolio)
    db_session.commit()
    
    assert portfolio.created_at.tzinfo is not None
    assert portfolio.updated_at.tzinfo is not None


def test_guardrails_audit_timestamp_is_aware(db_session):
    """GuardrailsAudit.timestamp must be timezone-aware."""
    audit = GuardrailsAudit(
        user_email="test@example.com",
        action="update",
        changes="{}",
    )
    db_session.add(audit)
    db_session.commit()
    
    assert audit.timestamp.tzinfo is not None


def test_portfolio_touch_history_timestamps_are_aware(db_session):
    """PortfolioTouchHistory timestamps must be timezone-aware."""
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
    
    assert touch.last_decision_timestamp.tzinfo is not None
    assert touch.created_at.tzinfo is not None
    assert touch.updated_at.tzinfo is not None
```

**Time:** 8 minutes

**Verification:** 
```bash
npm run test:backend -- tests/test_datetime_fixtures.py -v
```

All tests should pass ✓

---

## Tier 4: Developer Documentation (5 minutes)

### Action Item 4.1: Create CLAUDE.md Reference
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
Add to the "Best Practices" or "Testing" section of `/CLAUDE.md`:

```markdown
### Timezone Handling in Tests

- **Rule:** All `DateTime(timezone=True)` columns must use timezone-aware UTC datetimes
- **Use:** `now_utc()` from `tests.conftest` or `datetime.now(timezone.utc)`
- **Never:** `datetime.now()` when storing to the database
- **Why:** SQLite accepts naive datetimes (no validation), but Supabase PostgreSQL requires timezone-aware. Tests must match production behavior.
- **Reference:** See `docs/solutions/TIMEZONE_TESTING_GUIDE.md`

Example:
```python
# WRONG
timestamp=datetime.now()

# CORRECT
timestamp=now_utc()
```
```

**Time:** 2 minutes

### Action Item 4.2: Link Documentation in README
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
Add to `/docs/TESTING.md` or create a new section in `/README.md`:

```markdown
## Timezone Testing

See `docs/solutions/TIMEZONE_TESTING_GUIDE.md` for comprehensive guidance on:
- When to use naive vs timezone-aware datetimes
- SQLite vs PostgreSQL datetime handling
- Test fixture patterns
- Common mistakes and warning signs
```

**Time:** 2 minutes

---

## Tier 5: Infrastructure Validation (Optional, High Value)

### Action Item 5.1: Add Pre-commit Hook Validation
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
Create a simple hook in `.git/hooks/pre-commit` to warn about naive datetimes:

```bash
#!/bin/bash
# Warn about datetime.now() in backend code (not tests — tests are OK if they use now_utc)
NAIVE_DT=$(grep -r "datetime\.now()" backend/ --include="*.py" | grep -v "timezone.utc" | grep -v tests/ | grep -v ".venv" | grep -v "venv")
if [ -n "$NAIVE_DT" ]; then
    echo "⚠️  Warning: Found naive datetime.now() in production code:"
    echo "$NAIVE_DT"
    echo "Production code should use datetime.now(timezone.utc)"
fi
```

**Benefit:** Catches mistakes before they're committed

**Time:** 5 minutes (optional)

### Action Item 5.2: Add CI Check (GitHub Actions)
**Status:** [ ] Not Started [ ] In Progress [ ] Complete

**What to do:**
Add step to `.github/workflows/tests.yml`:

```yaml
- name: Check for naive datetimes in production code
  run: |
    RESULT=$(grep -r "datetime\.now()" backend/app --include="*.py" | grep -v "timezone.utc" || true)
    if [ -n "$RESULT" ]; then
      echo "❌ Found naive datetime.now() in production code:"
      echo "$RESULT"
      exit 1
    fi
    echo "✓ All production datetimes are timezone-aware"
```

**Benefit:** Automated enforcement across the team

**Time:** 5 minutes (optional)

---

## Execution Roadmap

### Phase 1: Immediate (Today, 10 minutes)
- [ ] 1.1: Add `now_utc()` to conftest.py
- [ ] 1.2: Fix `make_plan()` and `make_trade()`
- [ ] Run: `npm run test:backend`

### Phase 2: Audit & Fix (Today, 15 minutes)
- [ ] 2.1: Find all naive datetimes
- [ ] 2.2: Categorize findings
- [ ] 2.3: Fix Category A items
- [ ] Run: `npm run test:backend`

### Phase 3: Validation (Today, 10 minutes)
- [ ] 3.1: Create `test_datetime_fixtures.py`
- [ ] Run: `npm run test:backend -- tests/test_datetime_fixtures.py`

### Phase 4: Documentation (Today, 5 minutes)
- [ ] 4.1: Add note to CLAUDE.md
- [ ] 4.2: Link from README or docs

### Phase 5: Infrastructure (This Week, 5-10 minutes)
- [ ] 5.1: Add pre-commit hook (optional)
- [ ] 5.2: Add CI check (optional)

**Total Effort:** ~40 minutes (30 without optional infrastructure)

---

## Quality Gates

Before marking complete, verify:

- [ ] `npm run test:backend` passes (all tests)
- [ ] No new test failures introduced
- [ ] `grep -r "datetime.now()" backend/tests/ | grep -v "timezone.utc" | wc -l` is 0 or very small
- [ ] `test_datetime_fixtures.py` exists and passes
- [ ] Developers know where to find timezone guidance (docs/CLAUDE.md)
- [ ] Pre-commit hook (if implemented) works locally

---

## Long-Term Improvements

### If/When You Migrate Tests to PostgreSQL

All these changes make migration trivial:

1. Change `DATABASE_URL` from SQLite to PostgreSQL in conftest
2. Run `npm run test:backend`
3. **Any naive datetimes now fail immediately** (PostgreSQL validates)
4. Developers fix remaining issues with guidance from this doc
5. Tests now run against production DB type → No more SQLite/PostgreSQL mismatches

### Monitoring for Regression

Add to CI or regular checks:

```bash
# Monitor for creeping naive datetimes
grep -r "datetime\.now()" backend/tests/ | grep -v "timezone.utc" | grep -v ".venv"
# Should always return empty or very few lines
```

---

## Quick Reference: Where to Look

| What | File/Location |
|------|---------|
| Timezone helper | `backend/tests/conftest.py` (add `now_utc()`) |
| Fixture fixes | `backend/tests/conftest.py` (update `make_plan()` and `make_trade()`) |
| Validation test | `backend/tests/test_datetime_fixtures.py` (new file) |
| Full guide | `docs/solutions/TIMEZONE_TESTING_GUIDE.md` |
| Implementation guide | `docs/solutions/TIMEZONE_CONFTEST_IMPLEMENTATION.md` |
| Quick ref | `docs/solutions/TIMEZONE_QUICK_REFERENCE.md` |
| CLAUDE.md update | Search "Testing" section |

---

## Success Criteria

- [ ] Helper function `now_utc()` is available in conftest
- [ ] All naive `datetime.now()` in test fixtures replaced with `now_utc()`
- [ ] Validation test (`test_datetime_fixtures.py`) exists and passes
- [ ] Developers have clear guidance in docs
- [ ] No timezone-related test failures in CI
- [ ] Next developer who writes tests uses `now_utc()` automatically

---

## If You Get Stuck

1. **"How do I find the naive datetimes?"**
   → Run: `grep -rn "datetime.now()" backend/tests/ --include="*.py" | grep -v "timezone.utc"`

2. **"I don't understand the problem"**
   → Read: `docs/solutions/TIMEZONE_TESTING_GUIDE.md` (10 min read, explains everything)

3. **"Which ones should I fix?"**
   → If it stores to a `DateTime(timezone=True)` column → Fix it
   → See "Model Fields That Need Aware Datetimes" table in TIMEZONE_QUICK_REFERENCE.md

4. **"Tests are now failing"**
   → Check if you broke model defaults or imports
   → Run: `npm run test:backend` with verbose: `npm run test:backend -- -vv`
   → Revert last change and re-examine

---

## Notes for Stakeholders

**Why this matters:** Silent bugs that pass in SQLite tests but fail in production Supabase. Eliminates an entire category of production issues.

**When to do this:** Before scaling up test coverage or adding timezone-heavy features (earnings dates, trading windows, etc.)

**No downside:** Existing code continues to work. These are purely test-side improvements.

**Time investment:** 30 minutes now prevents hours of production debugging later.
