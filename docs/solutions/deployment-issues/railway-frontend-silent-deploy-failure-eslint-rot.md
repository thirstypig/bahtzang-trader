---
title: "Railway frontend serving stale build for 2 weeks because ESLint errors in untouched files blocked every redeploy attempt; CI was always green because CI doesn't run ESLint"
category: deployment-issues
tags: [railway, eslint, silent-failure, ci-drift, next-build, deployment, frontend, monorepo]
module: frontend (bahtzang-trader)
symptom: "First frontend deploy in 2 weeks (forex feature push) failed at 'next build' with 3 ESLint no-unused-vars errors in plans/ files that the push did not touch. The frontend service had been silently failing to redeploy since the errors were introduced — no banner, no alert, just an old build still serving traffic. CI showed green throughout the rot window."
root_cause: "Two-bug interaction: (1) Pre-existing dead-code lint errors had been merged earlier without notice because GitHub Actions CI runs only `npx tsc --noEmit && npx vitest run` — neither invokes ESLint. (2) `next build` (which Railway runs for production) DOES invoke ESLint with 'fail on error' semantics. Result: CI green, prod build red. Whenever frontend redeployed it failed; whenever CI ran it passed; the gap was invisible until something forced a fresh frontend redeploy."
severity: high
date_solved: 2026-05-06
time_to_resolve: "~10 minutes once Railway build log was inspected"
diagnosis_tools: [railway dashboard build logs, gh CLI, curl HTML chunk inspection, local 'next build' verification]
related_solutions:
  - deployment-issues/railway-silent-deploy-failure-pandas-ta.md
---

# Railway frontend silent deploy failure — ESLint rot, CI didn't catch it

## Symptoms

- A push to `main` containing a new feature with frontend changes deployed the **backend** service successfully but the **frontend** service kept serving a build from 2 weeks earlier.
- `https://www.bahtzang.com/forex` returned `HTTP 404` and loaded the not-found chunk; the new sidebar link wasn't visible anywhere.
- The `/` HTML had no reference to any `_next/static/chunks/app/forex/page.*.js` chunk — unambiguous evidence the new bundle never built.
- Railway dashboard for the frontend service showed the most recent **successful** deploy was 2 weeks ago. No "failed" banner. The latest attempt(s) appeared as failures only after clicking into the build log.
- GitHub Actions CI on the same commits was green — `npx tsc --noEmit` clean, `npx vitest run` 291/291.

## Investigation Steps

1. **Confirmed backend was deployed** — `curl /forex/symbols` returned 403 ("Not authenticated") and `/openapi.json` listed all forex routes. So the routing layer was right, the gap had to be in frontend.
2. **Confirmed frontend was NOT deployed** — `curl https://www.bahtzang.com/` HTML did not reference any `app/forex/page.*.js` chunk; `/forex` returned 404 with the not-found chunk loaded.
3. **Asked the user to check Railway dashboard.** They reported "deployment successful 2 weeks ago" — meaning Railway's UI was showing the *last successful* deploy, not the latest *attempt*. No new successes since.
4. **User pasted the build log** which ended:
   ```
   Failed to compile.
   ./src/app/plans/[id]/page.tsx
     7:33  Error: 'TradingGoal' is defined but never used.
   ./src/app/plans/page.tsx
     8:26  Error: 'TradingGoal' is defined but never used.
   ./src/components/PlanEquityCurve.tsx
     69:9  Error: 'firstValue' is assigned a value but never used.
   ```
5. **Confirmed CI gap** by reading `.github/workflows/tests.yml`: frontend job runs `tsc --noEmit` and `vitest run` only — no `next lint`, no `next build`. So CI never executed the check that Railway runs in production.

## Root Cause

Two-step failure mode:

**Step 1: rot accumulates silently.** A previous PR merged code with three unused-var ESLint errors (`TradingGoal` import in two `plans/` files, `firstValue` local in `PlanEquityCurve`). CI was green because CI doesn't run ESLint. The errors were dead weight, not behavior bugs — nothing surfaced in tests or runtime. They sat there for ~2 weeks.

**Step 2: rot reveals only on full redeploy.** Railway watches subtree paths — frontend service redeploys only when something under `frontend/` changes. For 2 weeks, all pushes were backend-only, so frontend never tried to rebuild. The forex feature push was the first push to touch `frontend/`. Railway tried to rebuild, `next build` ran ESLint, lint failed → build failed → deploy failed → frontend kept serving the 2-week-old bundle. Railway *did* mark the new deploys as failed, but the dashboard "most recent successful" view obscures this for casual glances.

This is a **CI-drift** problem: the checks that gate merges (CI) diverged from the checks that gate production (Railway's `next build`). Anything that fails the second but passes the first becomes a latent landmine.

## Solution

### 1. Fix the lint errors (the immediate unblock)

```diff
# frontend/src/app/plans/page.tsx
- import { InvestmentPlan, TradingGoal } from "@/lib/types";
+ import { InvestmentPlan } from "@/lib/types";

# frontend/src/app/plans/[id]/page.tsx
- import { InvestmentPlan, Trade, TradingGoal } from "@/lib/types";
+ import { InvestmentPlan, Trade } from "@/lib/types";

# frontend/src/components/PlanEquityCurve.tsx
- const firstValue = snapshots[0].total_value;
-
  const data = snapshots.map((s) => ({
```

### 2. Verify locally with the *real* production build command

Don't trust `tsc --noEmit` alone — run what Railway runs:

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://placeholder \
  NEXT_PUBLIC_SUPABASE_URL=https://placeholder.supabase.co \
  NEXT_PUBLIC_SUPABASE_ANON_KEY=placeholder \
  npx next build
```

Look for `Failed to compile` in the output. If it says `✓ Compiled successfully` and lists routes, it's safe to push.

### 3. Push, watch Railway redeploy, verify

```bash
# After push, poll until the new bundle ships
until curl -s https://www.bahtzang.com/ | grep -q "app/forex"; do sleep 20; done
```

Once the new chunk reference appears in the HTML, deploy is live.

## Prevention

### Add `next lint` to CI

The structural fix. Edit `.github/workflows/tests.yml` frontend job:

```diff
       - run: npm ci
       - run: npx tsc --noEmit
+      - run: npx next lint
       - run: npx vitest run
```

This makes CI fail-stop the moment any commit introduces a lint error, so the rot can never accumulate. Cost: ~5 seconds added to CI. Benefit: zero silent rot.

### Optional — make the pre-commit hook run the same

`.git/hooks/pre-commit` currently runs `tsc + pytest + vitest`. Adding `next lint` here would catch the issue *before* it even gets pushed, but the hook is already at ~5s per commit. Trade-off; CI is the floor, hook is a luxury.

### Optional — add a "stale frontend deploy" canary

If long stretches of backend-only work are expected, force a periodic frontend redeploy to surface rot fast. Either a scheduled GitHub Action that touches `frontend/.deploy-canary` weekly, or a `railway redeploy` cron. The CI fix above is strictly better — only do this if for some reason CI lint isn't viable.

### General principle: CI must run a strict superset of production-build checks

Whenever you split "what CI runs" from "what production build runs," anything that fails only the latter becomes a deploy-time landmine. The audit: list every check production runs (`next build`, `pip install`, schema migrations, etc.) and confirm CI runs each one with the same fail-stop semantics. Drift accumulates silently — you only learn about it when you can't afford to.

## Tests / Verification

The new doc workflow doesn't require a code-level test, but two checks belong in the regression set:

1. **CI runs `next lint`** — verifiable by inspecting `.github/workflows/tests.yml` and watching a future PR's CI logs.
2. **A deliberate unused-var commit (in a throwaway branch) is caught by CI before merge** — manual one-time verification when the lint check is added.

## Related

- `deployment-issues/railway-silent-deploy-failure-pandas-ta.md` — Sibling case on the **backend** service. Same shape: dashboard hides the failure, latest "successful" deploy is stale, real diagnosis comes from build logs. Worth reading both together — they're the two halves of "Railway-monorepo silent rot."
- `integration-issues/feature-module-isolation-pattern.md` — Architectural prevention; isolated feature modules reduce blast radius when one slice's lint rots.

## When this might recur

- Any new dev tool or check added to the production build pipeline (Railway `nixpacks`, Dockerfile, `next build`, `pip install`, `alembic upgrade`) without a parallel CI step. The forex feature push was the *trigger*, not the *cause*; the cause was a CI-drift configuration that allowed lint failures to accumulate undetected.
- Long stretches without redeploying a service (e.g., backend-only push windows, or services watching narrow subtree paths). The longer the gap, the more rot can accumulate.
- Migrations from one CI workflow to another that drops checks "we don't need anymore" without verifying production parity.

If any of these conditions apply: add a `next build`-equivalent step to CI before continuing.
