---
status: complete
priority: p2
issue_id: "033"
tags: [code-review, frontend, ux]
dependencies: []
---

# No User-Facing Error Feedback on Settings Page

## Problem Statement

When API calls fail on the Settings page, errors are logged to `console.error` but the user sees nothing. Additionally, the `saved` boolean is shared across all sections — changing frequency shows "Goal applied" under the wrong section.

**Found by:** TypeScript reviewer (P2 x2)

## Findings

- `frontend/src/app/settings/page.tsx:137-138` — `console.error("Failed to save:", err)` with no UI feedback
- `frontend/src/app/settings/page.tsx:117,217,318` — Single `saved` boolean shared across Trading Goal, Frequency, Risk Profile, and Fine-Tune sections
- Changing frequency triggers "Goal applied" under Trading Goal section
- User has no way to know if their settings actually persisted
- Critical for a financial application where settings affect real money

## Proposed Solutions

1. Add per-section `saved` and `error` state, or use a global toast component
2. Show error message near the action that failed
3. Consider optimistic rollback on failure

- **Effort:** Small
- **Risk:** None
