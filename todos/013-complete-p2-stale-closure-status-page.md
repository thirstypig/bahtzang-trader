---
status: complete
priority: p2
issue_id: "013"
tags: [code-review, bug, typescript]
dependencies: []
---

# Stale Closure in Status Page Interval

## Problem Statement

`runChecks()` closes over initial `services` state. The 5-minute interval always references stale data. eslint-disable comment masks the bug.

**Found by:** TypeScript reviewer, Pattern recognition (2 agents)

## Findings

- `frontend/src/app/status/page.tsx` lines 54-68: `runChecks()` captures the initial `services` state in a closure
- The 5-minute `setInterval` always references the stale initial state, not the current state
- An `eslint-disable` comment masks the missing dependency warning that would flag this bug
- Service check results may be incorrect or overwritten because the function operates on outdated data

## Proposed Solutions

Use functional state update `setServices(prev => ...)` or define service definitions as a constant. ~10 lines:

1. Replace direct `services` reference with a functional state update: `setServices(prev => ...)`
2. Alternatively, extract service definitions (names, URLs) as a constant outside the component
3. Remove the `eslint-disable` comment so future dependency issues are caught

## Technical Details

**Affected files:** `frontend/src/app/status/page.tsx` (lines 54-68)

**Effort:** Small (~10 lines)

## Acceptance Criteria

- [ ] `runChecks()` no longer closes over stale `services` state
- [ ] The 5-minute interval uses current state via functional update or constant definitions
- [ ] The `eslint-disable` comment is removed
- [ ] Service health checks reflect accurate, up-to-date results after each interval
- [ ] No React state update warnings or stale data bugs
