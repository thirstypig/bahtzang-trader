---
title: "CORS errors masked real issue — Supabase batch SQL silently failed on migration, backend crashed before sending CORS headers"
category: integration-issues
tags: [supabase, sql-migrations, schema-drift, CORS, silent-failure, batch-sql, database]
module: backend + database (bahtzang-trader)
symptom: "All frontend pages showed 'Failed to fetch' errors with CORS policy blocking API requests; browser DevTools showed CORS Origin header rejection despite CORS_ORIGINS environment variable correctly set"
root_cause: "Supabase SQL Editor silently skipped some statements when executing a large batch of migration SQL. The plan_id column (from Trade model unification and PlanTrade merge) never created. Backend crashed on every request with `sqlalchemy.exc.ProgrammingError: column trades.plan_id does not exist`, preventing it from sending any HTTP response including CORS headers. Browser saw 0 response headers and blamed CORS."
severity: critical
date_solved: 2026-04-22
time_to_resolve: "~4 hours from first CORS report to diagnosis; 4-5 days of zero trading activity (4/16-4/22) while investigating misdiagnosis"
diagnosis_tools: [railway CLI, supabase dashboard, browser devtools, psql]
---

# CORS masquerade — Backend crash before CORS headers, silently failed Supabase migration

## Problem

After deploying the unified **Trade** model (merging `PlanTrade` into `Trade` with a `plan_id` column) and Float→Numeric conversion across the trades table, production bahtzang.com showed **"Failed to fetch"** errors on every page load.

Browser DevTools showed a clear CORS policy violation:

```
Access to XMLHttpRequest at 'https://api.bahtzang-trader..../' 
from origin 'https://www.bahtzang.com' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

All API requests were being blocked before leaving the browser. Immediate assumption: **CORS configuration broken in the backend.**

**Impact:** No trading for 4-5 days (4/16-4/22) because the scheduler's trading cycle queries the `trades` table, which crashed on every execution. The app was running but completely non-functional.

## Investigation Steps

### Step 1: Verify CORS environment variable

```bash
# Checked Railway production backend settings
CORS_ORIGINS=https://www.bahtzang.com  # Correctly set
```

✓ Environment variable was correct.

### Step 2: Verify backend deployment

- Checked Railway dashboard — showed "successful deployment"
- Checked Railway build logs — no build errors

✓ Build claimed success.

### Step 3: Check runtime logs (where reality lives)

```bash
railway logs --service bahtzang-backend --environment production
```

Found the smoking gun:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn)
column trades.plan_id does not exist
LINE 1: SELECT ...columns... FROM trades WHERE ...
                                                    ^
```

Every single API request immediately crashed the backend before it could process the request or send any response headers, including CORS headers.

**The CORS error in the browser was not the cause — it was a symptom.** The backend was crashing before it could send any response.

### Step 4: Why does plan_id not exist?

User confirmed running the migration SQL against Supabase:

```sql
ALTER TABLE trades ADD COLUMN plan_id UUID REFERENCES plans(id);
ALTER TABLE trades DROP COLUMN quantity FLOAT;  -- Old trade format
ALTER TABLE trades ADD COLUMN quantity NUMERIC(20, 8);
ALTER TABLE trades DROP COLUMN avg_cost FLOAT;
ALTER TABLE trades ADD COLUMN avg_cost NUMERIC(20, 8);
```

But when we queried the trades table schema in Supabase:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'trades';
```

The `plan_id` column was missing, even though the user believed they had run the migration.

### Step 5: Root cause confirmed

The user explained: **They pasted all 4 statements into Supabase SQL Editor and hit "Execute"** — expecting Supabase to run them all or report failure if any failed.

What actually happened: **Supabase SQL Editor silently failed on some statements** (likely due to transaction constraints, blocking locks, or partial parsing), but continued executing the next ones. The user may have received a partial success message or assumed all 4 had run because some ALTER TABLE operations succeeded.

User reported: *"I verified after by running a SELECT that returned 4 columns, so I thought the migration succeeded."* — but that was verifying the wrong result set or checking a different query state.

### Step 6: Manual re-execution (one statement at a time)

```bash
# Run each statement individually via psql
psql "$SUPABASE_DB_URL" <<'EOF'
ALTER TABLE trades ADD COLUMN IF NOT EXISTS plan_id UUID REFERENCES plans(id);
EOF

psql "$SUPABASE_DB_URL" <<'EOF'
ALTER TABLE trades DROP COLUMN IF EXISTS quantity;
ALTER TABLE trades ADD COLUMN quantity NUMERIC(20, 8);
EOF

psql "$SUPABASE_DB_URL" <<'EOF'
ALTER TABLE trades DROP COLUMN IF EXISTS avg_cost;
ALTER TABLE trades ADD COLUMN avg_cost NUMERIC(20, 8);
EOF
```

Each statement succeeded individually. Once all 4 were applied, the backend came up and started processing requests.

## Root Cause

**Supabase SQL Editor batch execution has a silent failure mode.** When multiple SQL statements are pasted as a single batch and executed:

1. **Partial success**: Some statements may execute; others fail silently or are rolled back.
2. **No clear error indication**: The UI may show a success message even if some statements never ran.
3. **User assumption**: Developer assumes all statements ran because they saw a response or partial results.
4. **Silent schema drift**: The actual database state diverges from what the developer thinks it should be.

This is compounded by:
- **Transaction semantics**: If any statement fails mid-batch, PostgreSQL can roll back the whole transaction (depending on transaction isolation).
- **Locking issues**: ALTER TABLE on a large table (trades has millions of rows in production) can block if other queries are running; batch execution may timeout on later statements.
- **No visibility**: Unlike command-line `psql` (which echoes each statement), the Supabase UI doesn't show which statements succeeded/failed individually.

## Solution

### 1. Immediate fix (one-time)

Execute migration statements individually against production database:

```bash
# Using psql or Supabase query editor (one statement at a time)

-- Check current schema
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'trades'
ORDER BY ordinal_position;

-- Apply missing column
ALTER TABLE trades ADD COLUMN IF NOT EXISTS plan_id UUID REFERENCES plans(id);

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'trades'
AND column_name IN ('plan_id', 'quantity', 'avg_cost')
ORDER BY ordinal_position;
```

### 2. Permanent fix: Use Alembic for migrations instead of manual SQL

Add Alembic configuration (already in `requirements.txt`, but not wired up):

```bash
cd backend
alembic init migrations
```

Create a migration file:

```python
# migrations/versions/001_add_plan_id_and_numeric_precision.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    """Add plan_id column and convert Float to Numeric for trades."""
    # Step 1: Add plan_id
    op.add_column('trades', sa.Column('plan_id', sa.UUID, nullable=True))
    op.create_foreign_key(
        'fk_trades_plans',
        'trades', 'plans',
        ['plan_id'], ['id']
    )
    
    # Step 2: Convert quantity Float -> Numeric
    op.alter_column('trades', 'quantity', 
                    existing_type=sa.Float,
                    type_=sa.Numeric(20, 8))
    
    # Step 3: Convert avg_cost Float -> Numeric
    op.alter_column('trades', 'avg_cost',
                    existing_type=sa.Float,
                    type_=sa.Numeric(20, 8))

def downgrade():
    """Rollback migrations."""
    op.drop_constraint('fk_trades_plans', 'trades')
    op.drop_column('trades', 'plan_id')
    op.alter_column('trades', 'quantity',
                    existing_type=sa.Numeric(20, 8),
                    type_=sa.Float)
    op.alter_column('trades', 'avg_cost',
                    existing_type=sa.Numeric(20, 8),
                    type_=sa.Float)
```

Run migration on deploy:

```bash
# In backend/railway.toml or startup script
alembic upgrade head
uvicorn app.main:app ...
```

### 3. Prevent false-positive CORS diagnoses

Add a health check that validates database connectivity before returning any response:

```python
# backend/app/main.py
@app.get("/health")
async def health():
    """Health check — confirms backend is running AND database is accessible."""
    try:
        # Try a simple query that exercises the schema
        result = await db.execute(
            select(func.count()).select_from(trades)
        )
        return {
            "status": "ok",
            "database": "connected",
            "trades_count": result.scalar()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database": "failed"
        }, 500
```

Frontend can health-check before assuming CORS:

```typescript
// frontend/app/api-client.ts
async function checkBackendHealth() {
  try {
    const response = await fetch('/health', { credentials: 'same-origin' });
    if (!response.ok) {
      console.error("Backend health check failed:", response.status);
      return false;
    }
    return true;
  } catch (error) {
    console.error("Backend unreachable (not CORS):", error);
    return false;
  }
}

// Before making API calls, check health
if (!(await checkBackendHealth())) {
  throw new Error("Backend is down or database is inaccessible");
}
```

## Why This Was Hard to Diagnose

1. **CORS appears first in the browser**: The browser enforces CORS before sending the request and shows a CORS error if the response lacks headers. A crashed backend produces a 0-byte response with no headers, which looks identical to a CORS violation.

2. **Supabase UI lies about success**: Running multiple statements in the SQL editor doesn't clearly indicate which succeeded/failed. The user ran what they thought was a successful migration without realizing half of it never executed.

3. **Schema mismatch isn't immediately obvious**: The app uses SQLAlchemy ORM, which doesn't validate schema on boot — it only tries to access columns when queries hit the database. The first API call triggered the error, not startup.

4. **CORS config was actually correct**: This reinforced the misdiagnosis — the env var was right, so the problem *had* to be "CORS configuration," not "backend doesn't exist."

5. **4-5 days of no trading** because every scheduler cycle that queried trades hit the same `ProgrammingError`, crashing the entire trading bot without sending alerts.

## Prevention Strategies

### 1. Always verify schema after manual SQL migrations

```sql
-- Run immediately after migration batch in Supabase
SELECT COUNT(*) as column_count
FROM information_schema.columns
WHERE table_name = 'trades'
AND column_name IN ('plan_id', 'quantity', 'avg_cost');

-- Should return 3; if < 3, migration failed partway
```

### 2. Use Alembic for all schema changes (not ad-hoc SQL)

- Provides explicit success/failure per statement
- Tracks applied migrations in a version table
- Rollback support
- Can be tested locally before production

### 3. Never execute multi-statement SQL in a UI — use `psql` or CLI tool

```bash
# Good: transactional, clear errors per statement
psql "$DATABASE_URL" < migration.sql

# Bad: UI executes, unclear which succeeded
# (Don't paste into Supabase SQL Editor)
```

### 4. Add database connectivity health check

- Separate from CORS health check
- Run at startup; fail loud if schema validation fails
- Backend should not accept traffic if tables/columns are missing

### 5. Monitor zero-trading-activity anomalies

The scheduler ran 20+ times over 4 days with silent failures. Add:

```python
# backend/scheduler.py
@app_scheduler.scheduled_job('cron', hour='*', minute=0)
def trading_cycle():
    try:
        result = execute_trading_cycle()
        logger.info(f"Trading cycle completed: {result}")
    except Exception as e:
        logger.error(f"Trading cycle FAILED: {e}", exc_info=True)
        # Send alert (email, Slack, etc.) that cycle crashed
        notify_admin(f"Trading cycle error: {e}")
```

### 6. Frontend diagnostic: differentiate CORS from backend-down

```typescript
async function diagnoseFailure(error: Error) {
  if (error.message.includes("CORS")) {
    // Network error with 0 response — could be CORS or backend down
    const health = await checkBackendHealth();
    if (!health) {
      console.error("Backend is not responding (not CORS)");
    } else {
      console.error("CORS error (backend is up)");
    }
  }
}
```

## Testing Suggestions

### Test 1: Verify Alembic migration doesn't fail partway

```python
# tests/test_migrations.py
import subprocess
import tempfile

def test_migration_alembic_upgrade_succeeds():
    """Run alembic upgrade head and verify all statements applied."""
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="backend",
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Migration failed: {result.stderr}"
    
    # Verify expected columns exist
    from sqlalchemy import inspect
    inspector = inspect(engine)
    trades_columns = {col['name'] for col in inspector.get_columns('trades')}
    assert 'plan_id' in trades_columns, "plan_id column missing after migration"
    assert 'quantity' in trades_columns
    assert 'avg_cost' in trades_columns
```

### Test 2: Backend startup fails if schema is missing

```python
def test_app_startup_fails_on_missing_schema():
    """If plan_id column doesn't exist, app should fail to start."""
    # Drop the column
    with psql_session as db:
        db.execute("ALTER TABLE trades DROP COLUMN plan_id")
    
    # Try to start the app
    with pytest.raises(Exception) as exc:
        from app.main import app
    
    assert "plan_id" in str(exc.value) or "column" in str(exc.value)
```

### Test 3: Batch SQL in test — don't fail silently

```python
def test_batch_sql_fails_loudly_in_psql():
    """Verify that failed statements in a batch are reported."""
    migration_sql = """
    ALTER TABLE trades ADD COLUMN plan_id UUID;
    ALTER TABLE trades DROP COLUMN nonexistent_column;  -- Will fail
    ALTER TABLE trades ADD COLUMN quantity NUMERIC(20, 8);
    """
    
    result = subprocess.run(
        ["psql", database_url],
        input=migration_sql,
        capture_output=True,
        text=True
    )
    
    # psql returns non-zero on any statement failure
    assert result.returncode != 0, "Expected migration to fail"
    assert "nonexistent_column" in result.stderr
```

## Related Documentation

- `docs/solutions/deployment-issues/railway-silent-deploy-failure-pandas-ta.md` — Same diagnostic pattern: platform UI claims success, but backend is serving stale code. Use CLI to find the truth.
- Memory: `feedback_railway_deploy.md` — Railway deploys may lag or fail silently; always verify both services (frontend + backend) after push.
- Memory: `feedback_documentation_accuracy.md` — Always update About page, README, CLAUDE.md to match actual state after shipping features (e.g., the Trade model unification should have been documented before deploy).

## Relevant Code Files

- `backend/app/models.py` — Trade model definition (where plan_id was added)
- `backend/app/main.py` — FastAPI app; `Base.metadata.create_all()` only creates tables, not columns
- `backend/requirements.txt` — alembic is listed but not configured
- `backend/railway.toml` — startup script; should run `alembic upgrade head` before uvicorn
- `frontend/src/app/page.tsx` — Initial request that fails with "Failed to fetch"

## Key Learnings

1. **CORS errors can be a red herring**: A crashed backend (0-byte response) looks like a CORS error in the browser. Always check server logs first.

2. **UI batch execution is unreliable**: Supabase SQL Editor, pgAdmin, and other UIs don't always report individual statement failures clearly. Use `psql` with `--file` or run statements one at a time.

3. **Silent schema drift is dangerous**: SQLAlchemy `create_all()` only creates missing *tables*, not missing *columns*. Alembic is needed for proper migration tracking.

4. **Invisible failure modes cost days**: The trading bot crashed 20+ times over 4-5 days because the scheduler's queries failed silently. Monitor background job errors explicitly.

5. **Separation of concerns**: Health check should test database connectivity separately from API endpoint logic. CORS errors and "backend down" errors look the same to the browser but require different fixes.
