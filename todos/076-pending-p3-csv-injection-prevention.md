---
status: pending
priority: p3
issue_id: "076"
tags: [code-review, security, plans]
dependencies: []
---

# CSV injection in plan export

## Problem Statement
`plan.name` and `t.claude_reasoning` are written unescaped into CSV. A plan named `=cmd|'/c calc'!A1` could execute as a formula when opened in Excel. Low risk since this is a single-user app but worth fixing for defense-in-depth.

## Findings
- `backend/app/plans/routes.py:438-453` — CSV writer output

## Proposed Solution
Prefix any cell starting with `= + - @ \t \r` with a single quote:
```python
def csv_safe(value: str) -> str:
    s = str(value or "")
    if s and s[0] in "=+-@\t\r":
        return "'" + s
    return s
```

## Acceptance Criteria
- [ ] CSV cells cannot execute formulas
