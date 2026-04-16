---
status: complete
priority: p2
issue_id: "066"
tags: [code-review, typescript, plans, duplication]
dependencies: []
---

# Plan detail page duplicates TradeTable — reuse the existing component

## Problem Statement
`/plans/[id]/page.tsx` inlines a full trade table (~40 lines) that already exists as the `TradeTable.tsx` component used by the trades page. This duplicates rendering logic, action badges, and status formatting. When someone adds a column to TradeTable, the plan page drifts.

Similarly, the plans files reinvent `useEffect + useState + loading` instead of using the existing `useApiQuery` hook (which was explicitly created to prevent this pattern).

## Findings
- `frontend/src/app/plans/[id]/page.tsx:199-240` — inline trade table
- `frontend/src/components/TradeTable.tsx` — existing reusable component
- `frontend/src/lib/useApiQuery.ts` — exists with comment "Replaces the repeated useEffect + useState pattern"
- `frontend/src/app/plans/page.tsx:36-43` — reinvents the hook pattern
- `frontend/src/app/plans/[id]/page.tsx:36-43` — same
- `frontend/src/components/PlanPositions.tsx:17-24` — same
- `frontend/src/components/PlanEquityCurve.tsx:23-28` — same

## Proposed Solution
1. Replace inline table with `<TradeTable trades={trades} />`
2. Refactor all plans fetches to use `useApiQuery`
3. Extract shared `GOAL_LABELS` dict to `lib/plans.ts`

## Acceptance Criteria
- [ ] Plan detail page uses TradeTable component
- [ ] All plans fetches use useApiQuery
- [ ] GOAL_LABELS defined once
