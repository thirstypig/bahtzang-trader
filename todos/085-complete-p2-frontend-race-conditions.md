---
status: complete
priority: p2
issue_id: "085"
tags: [code-review, typescript, plans, concurrency]
dependencies: []
---

# Frontend fetch race conditions on navigation

## Problem Statement
When navigating from `/plans/1` to `/plans/2` quickly, the in-flight `getPlan(1)` request can resolve AFTER `getPlan(2)` and overwrite state with stale plan-1 data. Same in `PlanEquityCurve` and `PlanPositions`.

No AbortController or cleanup flag in the effects.

## Findings
- `frontend/src/app/plans/[id]/page.tsx:50-52` — no cleanup
- `frontend/src/components/PlanEquityCurve.tsx:24-31` — no cleanup
- `frontend/src/components/PlanPositions.tsx` — same pattern

## Proposed Solution
```tsx
useEffect(() => {
  let cancelled = false;
  getPlan(planId)
    .then(d => { if (!cancelled) setData(d); })
    .catch(e => { if (!cancelled) setError(e.message); })
    .finally(() => { if (!cancelled) setLoading(false); });
  return () => { cancelled = true; };
}, [planId]);
```

Or use AbortController for true cancellation.

## Acceptance Criteria
- [ ] Navigating between plans shows correct data every time
- [ ] In-flight requests canceled or ignored on unmount
