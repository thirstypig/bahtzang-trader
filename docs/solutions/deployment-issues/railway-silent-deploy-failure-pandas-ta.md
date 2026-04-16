---
title: "Railway backend serving stale code after silent build failures from removed PyPI package"
category: deployment-issues
tags: [railway, pypi, silent-failure, schema-drift, pandas-ta, deployment]
module: backend (bahtzang-trader)
symptom: "Backend was serving code from weeks ago despite Railway dashboard reporting successful deploys, missing /plans, /backtest, /earnings, and /admin/errors routes."
root_cause: "pandas-ta==0.3.14b0 was yanked from PyPI causing pip install to fail; Railway silently retained the last successful build while marking new deploys as successful in the dashboard, compounded by a pandas version conflict and Phase D schema drift (missing kelly_fraction, circuit_breaker_daily_pct columns)."
severity: high
date_solved: 2026-04-16
time_to_resolve: "~1 hour of investigation once CLI access confirmed"
diagnosis_tools: [railway CLI, psql]
---

# Railway silent deploy failure — pandas-ta yanked from PyPI + schema drift

## Symptoms

- Frontend pages loaded fine, but backend API endpoints returned 404s
- Railway dashboard claimed the latest deployments were "successful"
- Production was silently serving code from weeks ago (stale build)
- No obvious error surfaced in the main Railway UI view
- Missing routes in production: `/plans`, `/backtest`, `/earnings`, `/admin/errors`

## Investigation Steps

1. Checked frontend deployment first — it was healthy, ruling out the Next.js side.
2. Pushed an empty commit to force a redeploy. Railway reported "successful" again, but production behavior didn't change — old code still running.
3. Asked the user to check Railway dashboard settings (Auto Deploy, branch, env vars).
4. User couldn't find the "Auto Deploy" toggle — Railway's UI had been restructured and the setting wasn't where docs said it'd be.
5. **Breakthrough**: switched to the `railway` CLI to bypass the misleading web UI and inspect deployment state directly. The Deployments list revealed recent deploys were actually `FAILED`, not successful.

## Solution

### 1. Diagnostic commands (railway CLI)

```bash
railway login
railway link --workspace "Jimmy Chang's Projects" \
  --project bahtzang-trader \
  --service bahtzang-backend \
  --environment production
railway deployment list
# Showed most recent deploys as FAILED

railway logs <deployment_id> --build --lines 100
# Revealed: "Could not find a version that satisfies the requirement pandas-ta==0.3.14b0"
```

### 2. Fix 1 — pandas-ta version bump (PyPI yanked 0.3.x)

```diff
- pandas-ta==0.3.14b0
+ pandas-ta==0.4.71b0
```

### 3. Fix 2 — pandas compatibility (next build failed with dependency conflict)

```diff
- pandas==2.2.3
+ pandas==2.3.2
```

pandas-ta 0.4.71b0 requires `pandas>=2.3.2`; alpaca-py 0.36.0 accepts `pandas>=1.5.3`, so bumping pandas works for both.

### 4. Fix 3 — database schema migration

Once the app could build, it crashed on boot with:
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn)
column guardrails_config.kelly_fraction does not exist
```

SQLAlchemy's `Base.metadata.create_all()` only creates missing tables — it does NOT alter existing tables. Columns added to the `GuardrailsConfig` model during Phase D never propagated to the production database.

Ran against production DB:
```bash
psql "$DATABASE_URL" <<'EOF'
ALTER TABLE guardrails_config ADD COLUMN IF NOT EXISTS kelly_fraction FLOAT NOT NULL DEFAULT 0.25;
ALTER TABLE guardrails_config ADD COLUMN IF NOT EXISTS circuit_breaker_daily_pct FLOAT NOT NULL DEFAULT 0.05;
ALTER TABLE guardrails_config ADD COLUMN IF NOT EXISTS circuit_breaker_weekly_pct FLOAT NOT NULL DEFAULT 0.10;
ALTER TABLE guardrails_config ADD COLUMN IF NOT EXISTS respect_wash_sale BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE guardrails_config ADD COLUMN IF NOT EXISTS pdt_protection BOOLEAN NOT NULL DEFAULT TRUE;
EOF
```

After all three layers landed, the backend came up cleanly and the API started serving current code.

## Why This Happened

- **Supply chain issue**: PyPI removed the entire pandas-ta 0.3.x line; only 0.4.x remains. Any pinned install of `0.3.14b0` now fails at dependency resolution with no warning upstream.
- **Misleading Railway UI**: the main dashboard kept showing "deployment successful" — but that status referred to the last OLD build still serving traffic, not the new failing ones. The actual `FAILED` status was only visible in the Deployments tab listing and build logs. The CLI was the only reliable source of truth.
- **Incomplete schema migrations**: SQLAlchemy's `Base.metadata.create_all()` only creates missing tables — it does not `ALTER` existing ones. Columns added to the `GuardrailsConfig` model during Phase D never propagated to the production database, so the app booted into a schema mismatch as soon as the new code finally deployed.

## Prevention Strategies

1. **Monitor deployment status explicitly** — Don't trust "deployment successful" in Railway's UI; verify the actually-deployed code via `curl /openapi.json` or a dedicated `/version` endpoint. Silence is not success.

2. **Pin packages to compatible version ranges, not exact versions** — Use `pandas-ta>=0.4.71b0,<0.5` instead of `==0.3.14b0`. Exact pins become landmines when PyPI yanks a release; ranges let patch/minor bumps heal the build automatically.

3. **Set up deploy notifications** — Configure Railway to notify on FAILED deploys via Slack/Discord/email. Silent failures are only silent if nobody is listening.

4. **Add a build smoke test** — Before pushing, run `pip install -r requirements.txt` in a fresh virtualenv or a Docker container matching Railway's Python version. Catches yanked packages, missing system deps, and version conflicts locally in 30 seconds instead of during a prod outage.

5. **Use Alembic for schema migrations** — `Base.metadata.create_all()` only creates *new* tables; it silently ignores added columns. The project already lists alembic in `requirements.txt` — actually wire it up with `alembic init`, autogenerate revisions on model changes, and run `alembic upgrade head` on startup.

6. **Version endpoint** — Add `GET /version` returning the git SHA (injected at build time via `RAILWAY_GIT_COMMIT_SHA`) of the currently-running code. Makes "is this the latest build?" a one-line curl.

7. **Diagnostic CLI knowledge** — When Railway's UI lies, the CLI is the source of truth:
   ```bash
   railway login
   railway link --project <name> --service <backend> --environment production
   railway deployment list              # FAILED status shows clearly here
   railway logs <deployment_id> --build # The actual pip error
   ```

## Testing Suggestions

- **CI build gate**: GitHub Action that runs `pip install -r requirements.txt` in a clean `python:3.12-slim` container on every PR. Block merge if install fails.
- **Post-deploy smoke test**: After each push, poll `/openapi.json` for a known-new route (or `/version` for the expected SHA) and page on mismatch after 5 minutes.
- **Schema drift check**: On app startup, introspect `information_schema.columns` and compare against SQLAlchemy model columns; log `WARN` (or refuse to start in strict mode) when they diverge. Catches the `create_all()` blind spot without forcing a full Alembic rollout on day one.

## Related Documentation

- `docs/solutions/integration-issues/feature-module-isolation-pattern.md` — Pattern for self-contained feature modules; `create_all()` only picks up models imported in root `models.py`.
- Memory: `feedback_railway_deploy.md` documented the symptom (silent backend lag, misleading GitHub status) before this incident. This doc extends that with the CLI diagnosis workflow and supply-chain failure mode.

## Relevant Code Files

- `backend/requirements.txt` — pip dependency list; where the version pin lived
- `backend/app/models.py` — root models; line 11 comment "Import feature module models so create_all() picks them up"
- `backend/app/main.py` — `Base.metadata.create_all(bind=engine)` (no migrations, relies on import side-effects)
- `backend/railway.toml` — nixpacks builder, single-worker uvicorn

## Lessons

- Railway dashboard "deployment successful" can be misleading — always verify with `railway deployment list`
- Pin-and-forget dependencies risk PyPI yanks; monitor build logs, not just deploy status
- Schema migrations must ship before code that reads new columns
- When platform UI and reality disagree, the CLI tells the truth
