---
status: pending
priority: p2
issue_id: "050"
tags: [code-review, typescript, react]
dependencies: []
---

# Make useTheme/useSidebar throw when used outside provider

## Problem Statement
useAuth correctly throws when used outside AuthProvider, but useTheme and useSidebar silently return no-op defaults. Bugs from missing providers would be invisible.

## Findings
- `frontend/src/lib/theme.tsx` — useTheme returns default context silently when outside provider
- `frontend/src/lib/sidebar.tsx` — useSidebar returns default context silently when outside provider

## Proposed Solutions
Use `createContext<T | null>(null)` + throw in hook, matching the useAuth pattern.

```tsx
const ThemeContext = createContext<ThemeContextType | null>(null);

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
```

Apply the same pattern to useSidebar.

## Acceptance Criteria
- [ ] Using useTheme() outside ThemeProvider throws a descriptive error
- [ ] Using useSidebar() outside SidebarProvider throws a descriptive error
