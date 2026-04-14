---
status: pending
priority: p1
issue_id: "046"
tags: [code-review, performance, ssr]
dependencies: []
---

# Remove ThemeProvider mounted gate that blocks SSR

## Problem Statement
The `if (!mounted) return <div className="min-h-screen bg-surface" />` in ThemeProvider kills SSR output — user sees blank screen during hydration (50-200ms). The beforeInteractive script already prevents theme flash, making the mounted gate redundant.

## Findings
- `frontend/src/lib/theme.tsx:39-42` — mounted gate returns placeholder div, blocking all SSR content

## Proposed Solutions
Remove the mounted state and placeholder div. Use a lazy initializer for `useState` instead:

```tsx
const [theme, setTheme] = useState<Theme>(() => {
  if (typeof window === "undefined") return "dark";
  const raw = localStorage.getItem("theme");
  return raw === "light" || raw === "dark" ? raw : "dark";
});
```

The anti-flash script in `layout.tsx` handles the rest.

## Acceptance Criteria
- [ ] No blank screen during hydration
- [ ] SSR output contains actual page content
- [ ] Theme still loads correctly without flash
