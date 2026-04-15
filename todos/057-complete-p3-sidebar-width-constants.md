---
status: complete
priority: p3
issue_id: "057"
tags: [code-review, maintenance]
dependencies: []
---

# Export sidebar width constants

## Problem Statement
Sidebar widths 240/68 appear in both Sidebar.tsx (as Tailwind classes) and providers.tsx (as inline style). Changing width requires updating two files.

## Findings
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/app/providers.tsx`

## Proposed Solutions
Export SIDEBAR_WIDTH_EXPANDED = 240 and SIDEBAR_WIDTH_COLLAPSED = 68 from sidebar.tsx.

## Acceptance Criteria
- [ ] Width values defined in one place
- [ ] Both files reference the constants
