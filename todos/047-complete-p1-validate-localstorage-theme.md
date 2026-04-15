---
status: pending
priority: p1
issue_id: "047"
tags: [code-review, typescript, security]
dependencies: []
---

# Validate localStorage theme value at runtime

## Problem Statement
`localStorage.getItem("theme") as Theme | null` is an unsafe TypeScript cast. If localStorage contains an arbitrary string, it bypasses type checking silently.

## Findings
- `frontend/src/lib/theme.tsx:22` — unsafe cast of localStorage value to Theme type

## Proposed Solutions
Replace the unsafe cast with runtime validation:

```tsx
const raw = localStorage.getItem("theme");
const stored: Theme | null = raw === "light" || raw === "dark" ? raw : null;
```

## Acceptance Criteria
- [ ] Invalid localStorage values are treated as null and fall back to system preference
