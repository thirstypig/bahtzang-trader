---
status: pending
priority: p1
issue_id: "023"
tags: [code-review, architecture, trust, critical]
dependencies: []
---

# Trading Frequency Is Fully Inert — UI Misleads User

## Problem Statement

The `trading_frequency` field (1x/3x/5x per day) is stored in guardrails.json and displayed in the Settings UI, but the scheduler always runs exactly once at 9:35 AM ET. Selecting "5x/day" has zero effect. The user is misled into believing the bot trades 5 times per day when it only trades once.

**Found by:** Python reviewer (P1), Architecture strategist (MEDIUM), Code simplicity reviewer (HIGH), Agent-native reviewer (Critical)

## Findings

- `backend/app/scheduler.py:18-23` — Single hardcoded `CronTrigger` at 9:35 AM ET
- `backend/app/guardrails.py:87` — `trading_frequency` validated and saved but never read by scheduler
- `frontend/src/app/settings/page.tsx:107-110` — UI shows exact times ("9:35 AM, 1:00 PM, 3:45 PM ET")
- `backend/app/routes/guardrails.py:51-56` — Goals auto-suggest frequency, compounding the deception
- Full UI + API + validation + auto-suggestion pipeline built for a feature that does nothing

## Proposed Solutions

### Option A: Wire scheduler to read frequency (Recommended — Phase B in plan)
- `scheduler.py` reads `trading_frequency` from guardrails on startup
- Dynamic job reconfiguration via `scheduler.remove_job()` + `scheduler.add_job()`
- Add 90-second timeout per cycle to prevent overlap
- **Pros:** Completes the feature as designed in the plan
- **Cons:** 1-2 days effort
- **Effort:** Medium
- **Risk:** Low

### Option B: Remove frequency UI until wired up
- Remove frequency selector from Settings page
- Show "1x/day (9:35 AM ET)" as fixed text
- Keep the backend field for future use
- **Pros:** Honest UI, fast fix
- **Cons:** Loses the UI work already done
- **Effort:** Small
- **Risk:** Low

## Acceptance Criteria

- [ ] If Option A: Scheduler runs at correct times for selected frequency
- [ ] If Option B: UI no longer shows misleading frequency selector
- [ ] Bot behavior matches what the UI promises

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-04-10 | Code review found issue | 4 agents flagged independently |
