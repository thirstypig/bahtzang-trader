---
status: pending
priority: p3
issue_id: "099"
tags: [code-review, frontend, plans, quality]
dependencies: ["090"]
---

# Frontend: loadPlan Cancellation + State Consolidation

## Problem Statement

The plan detail page has two data-fetching paths: `loadPlan()` (no cancellation, called from event handlers) and the `useEffect` (with cancellation via `cancelled` flag). If the user navigates away during `handleToggleActive` or "Run Now", `loadPlan` still calls `setData`/`setLoading`/`setError` on an unmounted component.

Additionally, the plans list page's `loadPlans` has no cancellation at all.

## Findings

- **Source:** TypeScript Reviewer
- `plans/[id]/page.tsx:42-49` — `loadPlan()` has no cancellation
- `plans/[id]/page.tsx:52-71` — `useEffect` has cancellation (duplicated logic)
- `plans/page.tsx:42-53` — `loadPlans` + `useEffect` have zero cancellation

## Proposed Solutions

Replace `loadPlan()` with a `refreshKey` state counter. Event handlers increment it; the `useEffect` depends on it. Single fetch path with cancellation:

```typescript
const [refreshKey, setRefreshKey] = useState(0);
useEffect(() => {
  let cancelled = false;
  // ...fetch logic...
  return () => { cancelled = true; };
}, [user, planId, refreshKey]);

// In handlers:
setRefreshKey(k => k + 1);
```

- **Effort:** Small
- **Risk:** Low

## Acceptance Criteria

- [ ] Single data-fetching path with proper cancellation
- [ ] No state updates after component unmounts
- [ ] Plans list page also has cancellation

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from TypeScript reviewer | |
