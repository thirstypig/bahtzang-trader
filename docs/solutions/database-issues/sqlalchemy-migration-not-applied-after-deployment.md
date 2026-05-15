---
name: Unapplied database migrations blocked authentication after deployment
description: Railway auto-deployed new SQLAlchemy model columns but the live Supabase DB was not migrated, causing "column does not exist" 500s that made login and logout appear broken
type: database-issue
severity: critical
component: plans/models.py, database migrations, deployment pipeline
tags: [database-migration, schema-drift, deployment-sync, authentication-regression, railway-deployment, supabase, sqlalchemy]
date: 2026-05-12
status: resolved
---

# Unapplied Migrations Broke Authentication After Deployment

## Problem

After merging and deploying the oversight activity feature (PR #18), login and logout on bahtzang.com appeared completely broken. The Supabase OAuth flow completed normally, but the app returned no useful error — the dashboard just failed to load.

No browser-visible error. No 401 or 403. The auth flow *looked* broken even though Supabase and the JWT verification were fine.

## Root Cause

Railway auto-deployed the new code immediately, which included SQLAlchemy model changes that added four new columns:

- `Portfolio`: `decision_mode`, `strategy_id`, `strategy_params`
- `Trade`: `rules_recommendation`

SQLAlchemy does **not** run `create_all()` or any migration automatically in production. The Railway deployment only replaces the Python code — it has no awareness of the DB schema. The Supabase PostgreSQL instance still had the old schema.

On the first request after deploy, SQLAlchemy generated SQL referencing the new columns. PostgreSQL responded:

```
ERROR: column "decision_mode" does not exist
```

This raised an unhandled exception in the request handler → 500 → FastAPI's error response. Because the portfolio list endpoint (`GET /portfolios`) was called immediately on dashboard load (to populate the nav and dashboard widgets), *every page* crashed before rendering. The auth state in Supabase was valid but the app couldn't serve any page, making it appear that login itself was broken.

**The misleading symptom:** Auth lives in Supabase (not the FastAPI DB). The JWT round-trip was working. But since every authenticated request hits the DB, and the DB was returning 500s, users had no way to distinguish "auth broken" from "DB broken."

## Fix

Apply the missing migrations manually via psql against the live Supabase DB. The DATABASE_URL is in `backend/.env` under `DATABASE_URL`.

```bash
# Check which columns are missing
psql "$DATABASE_URL" -c "\d portfolios"
psql "$DATABASE_URL" -c "\d trades"

# Apply migrations (IF NOT EXISTS makes them idempotent — safe to re-run)
psql "$DATABASE_URL" -f backend/migrations/077_add_decision_mode.sql
psql "$DATABASE_URL" -f backend/migrations/078_add_rules_recommendation.sql

# Verify
psql "$DATABASE_URL" -c "\d portfolios"
psql "$DATABASE_URL" -c "\d trades"
```

Both migration files used `ADD COLUMN IF NOT EXISTS`, so running them twice was harmless.

After applying migrations, the app recovered immediately — no redeploy or restart needed. Railway was already running the new code; it just needed the DB to match.

## Why Tests Didn't Catch It

The test suite uses SQLite with `StaticPool` and `create_all()` (defined in `tests/conftest.py`). `create_all()` always creates all tables from the current model state — it never has schema drift. CI never sees a mismatch between model columns and DB schema.

The gap is structural: the test environment always has a perfect schema, production starts from historical state and must be migrated forward.

## Related Documentation

- [`supabase-batch-migration-silent-failure.md`](supabase-batch-migration-silent-failure.md) — Supabase's batch migration path has its own silent failure mode; run migrations one at a time via psql, not through the Supabase dashboard batch runner.
- [`sqlalchemy-decimal-float-sqlite-postgres-mismatch.md`](sqlalchemy-decimal-float-sqlite-postgres-mismatch.md) — Another class of production-only failures invisible to the SQLite test suite.
- [`sqlite-datetime-timezone-stripping.md`](sqlite-datetime-timezone-stripping.md) — Same root pattern: SQLite test environment masks type differences that appear in production PostgreSQL.
- [`../deployment-issues/railway-silent-deploy-failure-pandas-ta.md`](../deployment-issues/railway-silent-deploy-failure-pandas-ta.md) — Railway deploy failure patterns.

## Prevention

### Rule: DB Migrations Are Not Automatic on Railway

Railway has no migration runner. Deploying code that adds or changes SQLAlchemy model columns **always** requires a manual psql step against the live Supabase DB before or immediately after the deploy.

**Do not assume the deploy is complete until the schema matches the models.**

### Pre-Deploy Checklist for Schema Changes

Before merging any PR that adds/removes/renames columns:

1. **Write the migration file** in `backend/migrations/` with `ADD COLUMN IF NOT EXISTS` (or `DROP COLUMN IF EXISTS`).
2. **Verify locally** by running the migration against a copy of the prod DB dump or at minimum running `\d <table>` before and after.
3. **Apply to Supabase before merging** (or immediately after — the window is short since Railway deploys in ~2 minutes).
4. **Confirm with `\d <table>`** that all new columns appear in the live DB.

### Quick Schema Drift Check

After any deployment, run this to confirm the live DB matches the current models:

```bash
# Check portfolios columns
psql "$DATABASE_URL" -c "\d portfolios" | grep -E "decision_mode|strategy_id|strategy_params"

# Check trades columns
psql "$DATABASE_URL" -c "\d trades" | grep "rules_recommendation"
```

If the grep returns nothing, the migration wasn't applied.

### Improve Observability

The 500 on `GET /portfolios` was masked by the auth flow, making diagnosis slow. Two improvements worth adding:

1. **Health endpoint schema check**: `GET /health` could include a fast schema probe (e.g., `SELECT 1 FROM portfolios LIMIT 0`). A schema error would surface in Railway's health check rather than appearing as a user-facing auth failure.

2. **Structured error logging**: Catch `ProgrammingError` (SQLAlchemy's wrapper for "column does not exist") at the middleware level and log with severity=CRITICAL, rather than letting it bubble up as a generic 500.

### Deployment Runbook (schema-changing PRs)

```
1. Write migration SQL → backend/migrations/NNN_description.sql
2. Test locally: psql $LOCAL_DB_URL -f backend/migrations/NNN_description.sql
3. Merge PR to main (Railway deploy begins — ~2 minutes)
4. Apply migration to Supabase: psql $DATABASE_URL -f backend/migrations/NNN_description.sql
5. Verify: psql $DATABASE_URL -c "\d <affected_table>"
6. Smoke test: open bahtzang.com, log in, navigate to affected page
```

Steps 3 and 4 can overlap — the new code will return 500s until step 4 completes, but the window is short (under 5 minutes if you have the SQL ready).
