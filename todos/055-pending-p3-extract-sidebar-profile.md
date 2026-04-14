---
status: pending
priority: p3
issue_id: "055"
tags: [code-review, react, refactor]
dependencies: []
---

# Extract SidebarProfile sub-component

## Problem Statement
Sidebar.tsx handles 4 concerns (nav, logo, theme toggle, profile dropdown). The profile section (lines 162-209) has its own state and click-outside handler — it's a self-contained component.

## Findings
- `frontend/src/components/Sidebar.tsx:162-209`

## Proposed Solutions
Extract a SidebarProfile component for the profile button + dropdown.

## Acceptance Criteria
- [ ] Profile dropdown logic is in its own component
- [ ] Sidebar.tsx is shorter and cleaner
