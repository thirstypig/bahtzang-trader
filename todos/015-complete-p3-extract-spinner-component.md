---
status: complete
priority: p3
issue_id: "015"
tags: [code-review, quality, duplication]
dependencies: []
---

# Extract Shared Spinner Component

## Problem Statement

Identical spinner markup `<div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500" />` appears 6 times across the frontend. This duplication makes it harder to maintain consistent loading UI and increases the risk of divergent styling.

**Found by:** Code review

## Findings

- 6 files across the frontend contain the exact same spinner markup
- Any design change to the spinner requires updating all 6 locations
- Risk of partial updates leading to inconsistent loading indicators

## Proposed Solutions

Extract a `<Spinner />` component (e.g., `frontend/src/components/Spinner.tsx`) and replace all 6 instances with it.

## Technical Details

**Affected files:** 6 files across `frontend/src/`

**Effort:** Small

## Acceptance Criteria

- [ ] A reusable `<Spinner />` component exists in the components directory
- [ ] All 6 instances of the inline spinner markup are replaced with `<Spinner />`
- [ ] The spinner accepts optional size/color props for flexibility
- [ ] Visual appearance is unchanged
