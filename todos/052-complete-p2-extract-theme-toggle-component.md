---
status: pending
priority: p2
issue_id: "052"
tags: [code-review, react, duplication]
dependencies: []
---

# Extract shared ThemeToggleButton component

## Problem Statement
Sun/moon SVG icons for theme toggle are duplicated byte-for-byte in Sidebar.tsx and login/page.tsx.

## Findings
- `frontend/src/components/Sidebar.tsx:150-156` — sun/moon SVG toggle implementation
- `frontend/src/app/login/page.tsx:21-27` — identical sun/moon SVG toggle implementation

## Proposed Solutions
Create a `ThemeToggleButton` component that encapsulates icon selection and toggle logic.

```tsx
// frontend/src/components/ThemeToggleButton.tsx
export function ThemeToggleButton({ className }: { className?: string }) {
  const { theme, toggle } = useTheme();
  return (
    <button onClick={toggle} className={className} aria-label="Toggle theme">
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
```

## Acceptance Criteria
- [ ] Single ThemeToggleButton component used in both Sidebar and login page
