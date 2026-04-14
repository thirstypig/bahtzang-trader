---
status: complete
priority: p3
issue_id: "017"
tags: [code-review, quality, dead-code]
dependencies: []
---

# Remove Dead Code, Empty Directories, and Duplicate Nav Link

## Problem Statement

Approximately 15 lines of dead code, 2 empty directories, and 1 duplicate navigation link exist across the codebase. Dead code increases cognitive load and can mislead developers into thinking unused functions are part of the active system.

**Found by:** Code review

## Findings

- `frontend/src/lib/utils.ts`: unused `formatPercent` and `classNames` functions
- `frontend/src/lib/auth.tsx`: unused `accessToken` state variable
- `backend/app/scheduler.py`: unused `import asyncio`
- `backend/app/schwab_client.py`: unused `clear_token_cache` function
- `frontend/src/app/alerts/`: empty directory
- `frontend/src/app/paper-trading/`: empty directory
- `Navbar.tsx`: duplicate Analytics link in navigation

## Proposed Solutions

Delete all dead code, remove the empty directories, and remove the duplicate Analytics link.

## Technical Details

**Affected files:**
- `frontend/src/lib/utils.ts` (formatPercent, classNames)
- `frontend/src/lib/auth.tsx` (accessToken state)
- `backend/app/scheduler.py` (import asyncio)
- `backend/app/schwab_client.py` (clear_token_cache)
- `frontend/src/app/alerts/` (empty directory)
- `frontend/src/app/paper-trading/` (empty directory)
- `Navbar.tsx` (duplicate Analytics link)

**Effort:** Small

## Acceptance Criteria

- [ ] `formatPercent` and `classNames` are removed from `utils.ts`
- [ ] Unused `accessToken` state is removed from `auth.tsx`
- [ ] Unused `import asyncio` is removed from `scheduler.py`
- [ ] Unused `clear_token_cache` is removed from `schwab_client.py`
- [ ] Empty `alerts/` and `paper-trading/` directories are deleted
- [ ] Duplicate Analytics link in `Navbar.tsx` is removed
- [ ] No existing functionality is broken by any removal
