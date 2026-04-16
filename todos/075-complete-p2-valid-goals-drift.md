---
status: complete
priority: p2
issue_id: "075"
tags: [code-review, architecture, plans, duplication]
dependencies: []
---

# VALID_GOALS/VALID_PROFILES/VALID_FREQUENCIES duplicated between plans and guardrails

## Problem Statement
`plans/routes.py` hardcodes the goal/profile/frequency regex patterns instead of importing from `guardrails.py`. The goal list will drift silently — `plans/routes.py` hardcodes `maximize_returns|...` while `guardrails.py` derives from `TRADING_GOALS.keys()`.

## Findings
- `backend/app/plans/routes.py:20-22` — hardcoded regex strings
- `backend/app/guardrails.py:77` — `VALID_GOALS = "|".join(TRADING_GOALS.keys())`
- `backend/app/guardrails.py:82-84` — defined constants

## Proposed Solution
```python
from app.guardrails import VALID_GOALS, VALID_PROFILES, VALID_FREQUENCIES
```

Delete the duplicates in plans/routes.py.

## Acceptance Criteria
- [ ] Single source of truth for goal/profile/frequency validation
- [ ] Adding a new goal only requires one change
