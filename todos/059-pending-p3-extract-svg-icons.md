---
status: pending
priority: p3
issue_id: "059"
tags: [code-review, maintenance, readability]
dependencies: []
---

# Extract inline SVG icons to shared module

## Problem Statement
18 raw SVG path strings in the NAV constant make the navigation config unreadable (~1500 chars of opaque path data).

## Findings
- `frontend/src/components/Sidebar.tsx:30-61`

## Proposed Solutions
Extract to icons.ts module with named exports, or adopt heroicons/react (which these paths appear to come from).

## Acceptance Criteria
- [ ] Navigation config references named icons instead of raw path strings
