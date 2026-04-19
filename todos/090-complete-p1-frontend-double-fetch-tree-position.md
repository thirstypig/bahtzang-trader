---
status: pending
priority: p1
issue_id: "090"
tags: [code-review, frontend, performance, plans]
dependencies: []
---

# Frontend Double-Fetch: PlanPositions/PlanEquityCurve Unmount/Remount

## Problem Statement

On the plan detail page, `PlanPositions` and `PlanEquityCurve` are rendered in **different tree positions** during the loading state vs the loaded state. When loading finishes and `data` becomes non-null, React's reconciliation unmounts the loading-branch instances and mounts new ones in the main content branch. Each component has its own `useEffect` that fetches data on mount, so **both API calls fire twice** — once during loading and once after.

**Why it matters:** Every page view of a plan detail page triggers 4 API calls instead of 2 (positions + snapshots, doubled). This wastes Alpha Vantage API quota and slows page load.

## Findings

- **Source:** Performance Oracle
- `plans/[id]/page.tsx:96-99` — loading branch renders `<PlanPositions>` and `<PlanEquityCurve>`
- `plans/[id]/page.tsx:239-241` — loaded branch renders them again in a different parent `<div>`
- React sees different tree positions → unmount old instances → mount new instances → re-fetch

## Proposed Solutions

### Option A: Move components outside the conditional (Recommended)
```tsx
return (
  <div className="mx-auto max-w-5xl px-6 py-8">
    {loading ? <Spinner /> : <PlanHeader ... />}
    {/* Always in same tree position */}
    <div className="mt-6 grid gap-6 lg:grid-cols-2">
      <PlanPositions planId={planId} />
      <PlanEquityCurve planId={planId} />
    </div>
    {!loading && data && <TradeHistory ... />}
  </div>
);
```
- **Pros:** Eliminates double-fetch, React preserves component instances
- **Cons:** Components visible during plan header loading (minor layout shift)
- **Effort:** Small
- **Risk:** Low

## Acceptance Criteria

- [ ] `PlanPositions` and `PlanEquityCurve` only fetch data once per page load
- [ ] Components remain mounted when plan header data loads
- [ ] No visual regression in layout during loading state

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from performance oracle review | Tree position change causes React reconciliation to unmount/remount |
