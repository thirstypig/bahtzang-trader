---
status: pending
priority: p3
issue_id: "058"
tags: [code-review, correctness]
dependencies: []
---

# Fix isActive prefix matching edge case

## Problem Statement
`pathname.startsWith("/settings")` would also match a hypothetical `/settings-advanced`.

## Findings
- `frontend/src/components/Sidebar.tsx:72`

## Proposed Solutions
Use `pathname === href || pathname.startsWith(href + "/")` for precise matching.

## Acceptance Criteria
- [ ] Active state only matches exact path or child paths, not prefix collisions
