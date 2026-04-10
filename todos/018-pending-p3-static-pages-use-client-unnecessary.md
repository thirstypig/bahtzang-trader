---
status: pending
priority: p3
issue_id: "018"
tags: [code-review, performance, nextjs]
dependencies: []
---

# Static Pages Unnecessarily Use "use client"

## Problem Statement

Four pages (`about`, `docs`, `roadmap`, `changelog`) render purely static content with no hooks, event handlers, or browser APIs. They are marked with `"use client"` unnecessarily, which opts them out of Next.js Server Component benefits: no server-side rendering, larger client bundle, and slower initial page load.

**Found by:** Code review

## Findings

- `frontend/src/app/about/page.tsx`: static content, no client-side interactivity
- `frontend/src/app/docs/page.tsx`: static content, no client-side interactivity
- `frontend/src/app/roadmap/page.tsx`: static content, no client-side interactivity
- `frontend/src/app/changelog/page.tsx`: static content, no client-side interactivity
- All four pages only render JSX with no `useState`, `useEffect`, `onClick`, or other client-only features

## Proposed Solutions

Remove the `"use client"` directive from all four pages so they render as Server Components. This reduces the client JavaScript bundle and enables static generation at build time.

## Technical Details

**Affected files:**
- `frontend/src/app/about/page.tsx`
- `frontend/src/app/docs/page.tsx`
- `frontend/src/app/roadmap/page.tsx`
- `frontend/src/app/changelog/page.tsx`

**Effort:** Small

## Acceptance Criteria

- [ ] `"use client"` is removed from all four pages
- [ ] Pages render correctly as Server Components
- [ ] No client-side hooks or browser APIs are used in these pages
- [ ] Build completes without errors
