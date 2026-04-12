---
status: pending
priority: p1
issue_id: "022"
tags: [code-review, security, api, critical]
dependencies: ["021"]
---

# No Kill Switch Deactivation API — One-Way Trap

## Problem Statement

`POST /killswitch` only activates the kill switch. There is no API endpoint to deactivate it. Combined with Railway's ephemeral filesystem, this creates an operational trap: you can't deactivate via API, but deploys silently deactivate it.

**Found by:** Security sentinel (C2 CRITICAL), Agent-native reviewer (Critical)

## Findings

- `backend/app/routes/guardrails.py:65-71` — `/killswitch` only sets `kill_switch: True`
- `backend/app/guardrails.py:94` — `GuardrailsUpdate` deliberately omits `kill_switch`
- No programmatic recovery path after kill switch activation
- Once activated, only recovery is manual file edit on server or redeploy (which resets everything)

## Proposed Solutions

### Option A: Add POST /killswitch/deactivate (Recommended)
- New endpoint requiring a `reason` string parameter
- Log the deactivation with timestamp and reason
- **Pros:** Maintains deliberate-action safety while enabling recovery
- **Cons:** Small effort
- **Effort:** Small
- **Risk:** Low

## Acceptance Criteria

- [ ] Kill switch can be deactivated via API
- [ ] Deactivation requires explicit confirmation (reason string)
- [ ] Deactivation is logged with timestamp

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-04-10 | Code review found issue | 2 agents flagged |
