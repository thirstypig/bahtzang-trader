---
status: pending
priority: p2
issue_id: "054"
tags: [code-review, responsive, ux]
dependencies: []
---

# Add mobile responsive behavior for sidebar

## Problem Statement
Sidebar is fixed at 68px minimum width with no responsive breakpoints. On viewports under 400px, only ~264px remains for content. No hamburger menu or overlay mode.

## Findings
- `frontend/src/components/Sidebar.tsx` — no responsive breakpoints or mobile behavior
- `frontend/src/lib/sidebar.tsx` — no awareness of viewport size

## Proposed Solutions
Auto-collapse below `md` breakpoint. Add overlay mode for mobile with backdrop and hamburger button.

```tsx
// In SidebarProvider, add viewport awareness
useEffect(() => {
  const mq = window.matchMedia("(max-width: 768px)");
  const handler = (e: MediaQueryListEvent) => {
    if (e.matches) setExpanded(false);
  };
  mq.addEventListener("change", handler);
  if (mq.matches) setExpanded(false);
  return () => mq.removeEventListener("change", handler);
}, []);
```

Add overlay backdrop and hamburger toggle button for mobile viewports.

## Acceptance Criteria
- [ ] Sidebar works on mobile viewports
- [ ] Content is not squeezed on small screens
