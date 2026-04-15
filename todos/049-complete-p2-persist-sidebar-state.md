---
status: pending
priority: p2
issue_id: "049"
tags: [code-review, ux, react]
dependencies: []
---

# Persist sidebar expanded/collapsed state to localStorage

## Problem Statement
Sidebar resets to expanded on every page load. ThemeProvider correctly persists but SidebarProvider does not. UX regression for users who prefer collapsed sidebar.

## Findings
- `frontend/src/lib/sidebar.tsx` — no localStorage read on mount or write on change

## Proposed Solutions
Add localStorage read on mount and write on change, same pattern as ThemeProvider.

```tsx
const [expanded, setExpanded] = useState<boolean>(() => {
  if (typeof window === "undefined") return true;
  const stored = localStorage.getItem("sidebar-expanded");
  return stored === null ? true : stored === "true";
});

useEffect(() => {
  localStorage.setItem("sidebar-expanded", String(expanded));
}, [expanded]);
```

## Acceptance Criteria
- [ ] Sidebar state persists across page refreshes and navigation
