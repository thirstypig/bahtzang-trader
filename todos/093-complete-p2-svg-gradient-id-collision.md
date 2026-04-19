---
status: pending
priority: p2
issue_id: "093"
tags: [code-review, frontend, plans, bug]
dependencies: []
---

# SVG Gradient ID Collision in PlanEquityCurve

## Problem Statement

`PlanEquityCurve` uses a hardcoded SVG gradient `id="planEquityGrad"`. On the plan detail page, two instances are mounted simultaneously (loading branch + loaded branch, or if the double-fetch issue is fixed, potentially in other layouts). Duplicate SVG `id` attributes cause the second chart's gradient to reference the first's definition, producing incorrect rendering.

## Findings

- **Source:** TypeScript Reviewer
- `PlanEquityCurve.tsx:85` — `id="planEquityGrad"` is static
- Two instances can coexist during the loading→loaded transition

## Proposed Solutions

Append `planId` to the gradient ID:
```tsx
<linearGradient id={`planEquityGrad-${planId}`} ...>
```
And reference it: `fill={`url(#planEquityGrad-${planId})`}`

- **Effort:** Trivial
- **Risk:** None

## Acceptance Criteria

- [ ] Each PlanEquityCurve instance uses a unique gradient ID
- [ ] Chart renders correctly when multiple instances coexist

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from TypeScript reviewer | Real rendering bug, not theoretical |
