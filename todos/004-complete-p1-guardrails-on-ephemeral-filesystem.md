---
status: pending
priority: p1
issue_id: "004"
tags: [code-review, security, infrastructure, critical]
dependencies: []
---

# Guardrails Stored on Ephemeral Filesystem -- Lost on Redeploy

## Problem Statement

Guardrails are stored in `guardrails.json` on disk. Railway uses ephemeral filesystems -- any changes (including kill switch activation) are lost on redeploy. The kill switch -- the most critical safety mechanism -- silently deactivates on every deployment.

**Found by:** Security sentinel, Architecture strategist, Performance oracle (3 agents)

## Findings

- `backend/app/guardrails.py`: guardrails configuration is read from and written to `guardrails.json` on the local filesystem
- Railway's filesystem is ephemeral -- all file changes are discarded on every deploy, restart, or crash recovery
- If the kill switch is activated to halt trading, a subsequent deploy silently resets it to the default (off) state
- Any runtime guardrail adjustments (position limits, max investment caps) are also lost
- There is no audit trail for guardrail changes
- This creates a dangerous false sense of security: operators believe the kill switch is active, but it was silently deactivated

## Proposed Solutions

Move guardrails configuration to the PostgreSQL database (~50-80 lines):

1. Create a `guardrails_config` table with columns for each guardrail setting
2. Add a `guardrails_audit_log` table to track all changes with timestamps and who/what made them
3. Replace file read/write operations in `guardrails.py` with database queries
4. Seed default values on first run via a migration
5. Add audit logging for every guardrail change

## Technical Details

**Affected files:** `backend/app/guardrails.py`

**Effort:** Medium (~50-80 lines)

## Acceptance Criteria

- [ ] Guardrails configuration is stored in PostgreSQL, not on the filesystem
- [ ] A `guardrails_config` table exists with appropriate schema
- [ ] Kill switch state persists across deploys and restarts
- [ ] All guardrail changes are audit-logged with timestamps
- [ ] Default guardrail values are seeded on first run
- [ ] `guardrails.json` file dependency is fully removed
- [ ] Existing API endpoints (`/guardrails`, `/killswitch`) work with the new storage backend
