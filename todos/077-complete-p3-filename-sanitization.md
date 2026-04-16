---
status: complete
priority: p3
issue_id: "077"
tags: [code-review, security, plans]
dependencies: []
---

# Export filename not sanitized — Content-Disposition injection

## Problem Statement
`safe_name = plan.name.replace(" ", "-").lower()` doesn't strip special chars. A plan named `"; attachment; filename="evil.exe` would break the Content-Disposition header.

## Findings
- `backend/app/plans/routes.py:456-461` — filename generation

## Proposed Solution
```python
safe_name = re.sub(r'[^a-z0-9\-]', '', plan.name.replace(" ", "-").lower())[:50]
```

## Acceptance Criteria
- [ ] Filenames contain only [a-z0-9-]
- [ ] Max 50 chars
