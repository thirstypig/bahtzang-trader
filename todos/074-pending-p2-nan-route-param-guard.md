---
status: pending
priority: p2
issue_id: "074"
tags: [code-review, typescript, plans]
dependencies: []
---

# Plan detail page has no guard against NaN route param

## Problem Statement
`const planId = Number(params.id)` — if params.id is missing/malformed, planId becomes NaN. The page then makes API calls to `/plans/NaN/positions` which either 404s or hits unexpected behavior.

## Findings
- `frontend/src/app/plans/[id]/page.tsx:26` — `const planId = Number(params.id)` with no guard

## Proposed Solution
```tsx
const planId = Number(params.id);
if (Number.isNaN(planId) || planId <= 0) {
  return <NotFound />;
}
```

## Acceptance Criteria
- [ ] Invalid route params show NotFound
- [ ] No /plans/NaN/... API calls
