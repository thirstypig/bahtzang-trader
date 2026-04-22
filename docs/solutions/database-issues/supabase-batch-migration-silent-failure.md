---
title: "Migration Silently Fails When Run as Batch in Supabase SQL Editor"
date_solved: "2026-04-22"
severity: critical
affected_components:
  - database-migrations
  - production-deployment
  - backend-api
symptoms:
  - "CORS policy errors in browser on all API requests"
  - "Failed to fetch on every authenticated page"
  - "Backend crash: column trades.plan_id does not exist"
  - "4-5 days of no automated trading (scheduler crash)"
root_cause_category: database-issues
tags:
  - supabase
  - migrations
  - cors-masking
  - batch-execution
  - postgresql
related:
  - ../deployment-issues/railway-silent-deploy-failure-pandas-ta.md
---

# Migration Silently Fails When Run as Batch in Supabase SQL Editor

## Problem

After deploying the unified Trade model (067-fix: merging PlanTrade into Trade) and Float→Numeric conversion (071-fix), the production app at bahtzang.com showed "Failed to fetch" errors on every page. Browser DevTools showed CORS policy errors blocking all requests to the backend.

The bot stopped trading for 4-5 days (4/16 to 4/22) because the scheduler's trading cycle crashed on every attempt.

## Symptoms

- Browser: `Access to fetch at '...bahtzang-backend.../trades' from origin 'https://www.bahtzang.com' has been blocked by CORS policy`
- Every authenticated page showed "Failed to fetch"
- Railway dashboard showed successful deploy
- Railway build logs showed clean build

## Investigation

### Step 1: Check CORS config
```bash
railway variables | grep CORS
# CORS_ORIGINS = https://www.bahtzang.com  ← Correct
```
CORS config was fine. Red herring.

### Step 2: Check runtime logs
```bash
railway logs | tail -30
```
Found the real error:
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn)
column trades.plan_id does not exist
```

### Step 3: Verify migration applied
```sql
SELECT column_name FROM information_schema.columns WHERE table_name = 'trades';
```
Result: `plan_id` was **NOT** in the list. The migration had not applied despite the user running it and seeing "success".

### Step 4: Re-run migration in pieces
Ran statements one group at a time — each succeeded individually:
```sql
-- Group 1: Add columns
ALTER TABLE trades ADD COLUMN plan_id INTEGER REFERENCES plans(id) ON DELETE RESTRICT;
ALTER TABLE trades ADD COLUMN alpaca_order_id VARCHAR(64);
-- ✅ Success

-- Group 2: Type conversions
ALTER TABLE trades ALTER COLUMN quantity TYPE DOUBLE PRECISION;
ALTER TABLE trades ALTER COLUMN price TYPE NUMERIC(14,4);
-- ✅ Success

-- Group 3: Indexes
CREATE INDEX IF NOT EXISTS ix_trades_plan_timestamp ON trades (plan_id, timestamp DESC);
-- ✅ Success
```

## Root Cause

**Supabase SQL Editor silently fails on some statements when executing a large batch.** The user ran ~90 lines of SQL as one block. Some statements executed, others were silently skipped. The editor reported "success" but not all ALTER TABLE statements applied.

The user's first verification query happened to check the wrong thing (returned "4 columns" from a different query), creating a false positive that the migration had worked.

## Key Insight: CORS Errors Mask Backend Crashes

When a FastAPI backend crashes with a 500 error before the CORS middleware runs, it doesn't send `Access-Control-Allow-Origin` headers. The browser then reports this as a "CORS policy" violation instead of showing the actual 500 error.

**Rule:** When you see CORS errors on a deployed backend where CORS config is correct, check `railway logs` for the actual server error. The CORS message is a red herring.

## Prevention

1. **Run migration SQL in small groups** in Supabase SQL Editor (5-10 statements at a time), not as one giant batch
2. **Always verify with a column check** after running migrations:
   ```sql
   SELECT column_name, data_type FROM information_schema.columns
   WHERE table_name = 'trades' ORDER BY ordinal_position;
   ```
3. **Deploy code and migration atomically** — don't push code that expects new columns before confirming the migration applied
4. **Check `railway logs`** (not just the dashboard) when CORS errors appear on a deployed app
5. **Consider Alembic migrations** instead of manual SQL for complex schema changes — they track what's been applied

## Related

- [Railway Silent Deploy Failure](../deployment-issues/railway-silent-deploy-failure-pandas-ta.md) — same theme: Railway/Supabase appear fine but backend is broken. Diagnosis requires checking logs, not dashboards.

## Timeline

| Date | Event |
|------|-------|
| 4/16 | Last successful trade |
| 4/18-21 | Code deployed expecting `plan_id` column |
| 4/22 AM | User reports CORS errors |
| 4/22 AM | Diagnosed via `railway logs` → column missing |
| 4/22 AM | Re-ran migration in groups → all succeeded |
| 4/22 AM | App restored, bot resumed trading |
