---
status: complete
priority: p3
issue_id: "056"
tags: [code-review, typescript, cleanup]
dependencies: []
---

# Remove unused setExpanded from sidebar context

## Problem Statement
SidebarContext exposes setExpanded but no consumer uses it — only toggle and expanded are consumed.

## Findings
- `frontend/src/lib/sidebar.tsx`

## Proposed Solutions
Remove setExpanded from the interface and provider value.

## Acceptance Criteria
- [ ] setExpanded removed from context
- [ ] Build passes
