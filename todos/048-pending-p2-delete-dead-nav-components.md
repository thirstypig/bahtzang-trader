---
status: pending
priority: p2
issue_id: "048"
tags: [code-review, dead-code, cleanup]
dependencies: []
---

# Delete dead Navbar.tsx and AdminNav.tsx (240 lines)

## Problem Statement
Both files are orphaned — no imports anywhere in the codebase. They use old hardcoded zinc colors and will confuse future development.

## Findings
- `frontend/src/components/Navbar.tsx` (202 lines) — no imports found in codebase
- `frontend/src/components/AdminNav.tsx` (38 lines) — no imports found in codebase

## Proposed Solutions
Delete both files.

## Acceptance Criteria
- [ ] Files deleted
- [ ] Build passes
- [ ] No import errors
