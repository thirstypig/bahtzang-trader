---
status: complete
priority: p3
issue_id: "078"
tags: [code-review, performance, plans, react]
dependencies: []
---

# PlanAllocationChart re-renders on every parent state change

## Problem Statement
The donut chart has no `React.memo` and its `data` array is rebuilt every render. Recharts re-tweens the pie animation on every parent update (toggling, running, runResult). Visual flicker.

## Findings
- `frontend/src/components/PlanAllocationChart.tsx` — no memo, no useMemo

## Proposed Solution
```tsx
export default React.memo(PlanAllocationChart);
```

And inside:
```tsx
const data = useMemo(
  () => plans.map(...),
  [plans],
);
```

## Acceptance Criteria
- [ ] Chart doesn't re-render when parent state changes
- [ ] No animation flicker on unrelated updates
