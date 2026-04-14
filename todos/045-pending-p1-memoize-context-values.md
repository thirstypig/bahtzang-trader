---
status: pending
priority: p1
issue_id: "045"
tags: [code-review, performance, react]
dependencies: []
---

# Memoize ThemeProvider and SidebarProvider context values

## Problem Statement
Both providers create new object references on every render, causing full-tree re-render cascade. Every theme toggle re-renders the entire app including all charts and data tables.

## Findings
- `frontend/src/lib/theme.tsx:45` — ThemeProvider context value is a new object on every render
- `frontend/src/lib/sidebar.tsx:20` — SidebarProvider context value is a new object on every render
- `frontend/src/lib/auth.tsx` — AuthProvider value also needs memoization

## Proposed Solutions
Wrap context values in `useMemo`, stabilize toggle functions with `useCallback`. Also memoize AuthProvider value at `frontend/src/lib/auth.tsx`.

```tsx
const toggle = useCallback(() => setTheme(prev => prev === "dark" ? "light" : "dark"), []);
const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);
```

Apply the same pattern to SidebarProvider and AuthProvider.

## Acceptance Criteria
- [ ] Context values are referentially stable when state hasn't changed
- [ ] Toggling theme does not re-render Sidebar
- [ ] Toggling sidebar does not re-render theme consumers
