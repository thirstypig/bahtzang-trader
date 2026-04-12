---
status: pending
priority: p1
issue_id: "021"
tags: [code-review, security, infrastructure, critical]
dependencies: []
---

# Guardrails on Ephemeral Filesystem — Kill Switch Resets on Deploy

## Problem Statement

Guardrails config (including the kill switch) is stored in `guardrails.json` on disk. Railway uses ephemeral filesystems — every deploy, restart, or crash recovery resets the file to its committed state. The kill switch silently deactivates on routine deploys. This is a safety-critical defect for a trading bot managing real money.

**Found by:** Architecture strategist, Security sentinel, Performance oracle (3 agents independently)

## Findings

- `backend/app/guardrails.py:15` — `GUARDRAILS_PATH` points to local file
- `backend/app/guardrails.py:112-136` — `load_guardrails()` / `save_guardrails()` use raw file I/O
- No file locking, no atomic writes — concurrent requests can corrupt/lose data (race condition)
- No schema validation on loaded config — tampered file loaded without complaint
- Railway ephemeral FS means all runtime config changes are lost on deploy
- Previous todo 004 flagged this but was marked complete without the migration being implemented

## Proposed Solutions

### Option A: Migrate to PostgreSQL (Recommended)
- Create `guardrails_config` table with one row
- Replace `load_guardrails()` / `save_guardrails()` with DB queries
- Database is already connected via SQLAlchemy
- **Pros:** Persistent, atomic, concurrent-safe, audit-ready
- **Cons:** ~2 hours effort, requires migration
- **Effort:** Medium
- **Risk:** Low

### Option B: Add file locking + atomic writes (Short-term)
- Add `threading.Lock` around read-modify-write
- Use write-to-temp-then-rename pattern
- **Pros:** Quick fix for race conditions
- **Cons:** Does NOT solve ephemeral filesystem problem
- **Effort:** Small
- **Risk:** Low (but incomplete)

## Acceptance Criteria

- [ ] Kill switch state persists across Railway deploys
- [ ] Guardrail changes persist across restarts
- [ ] Concurrent config updates don't lose data
- [ ] Loaded config is validated against schema

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-04-10 | Code review found issue | 3 agents flagged independently |
