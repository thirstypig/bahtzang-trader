---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, quality]
dependencies: []
---

# datetime.utcnow Deprecated Since Python 3.12

## Problem Statement

`datetime.utcnow` deprecated since Python 3.12, returns naive datetime. `guardrails.py` uses `datetime.now(timezone.utc)` (aware). Comparing naive vs aware can raise TypeError or produce wrong results in daily trade count.

**Found by:** Python reviewer, Pattern recognition, Security sentinel (3 agents)

## Findings

- `backend/app/models.py` line 14: uses `datetime.utcnow` which is deprecated since Python 3.12
- `datetime.utcnow` returns a naive datetime (no timezone info)
- `backend/app/guardrails.py` uses `datetime.now(timezone.utc)` which returns an aware datetime
- Comparing naive vs aware datetimes can raise `TypeError` or produce incorrect results
- The daily trade count logic is affected, potentially allowing trades to bypass the daily limit

## Proposed Solutions

Change to `default=lambda: datetime.now(timezone.utc)` and `DateTime(timezone=True)`. 2 lines:

1. Replace `datetime.utcnow` with `datetime.now(timezone.utc)` in the model default
2. Change the column type to `DateTime(timezone=True)` to store timezone-aware datetimes

## Technical Details

**Affected files:** `backend/app/models.py` (line 14)

**Effort:** Small (2 lines)

## Acceptance Criteria

- [ ] `datetime.utcnow` is replaced with `datetime.now(timezone.utc)` in the default
- [ ] The column type uses `DateTime(timezone=True)`
- [ ] All datetime comparisons between `models.py` and `guardrails.py` use timezone-aware datetimes
- [ ] Daily trade count calculation produces correct results
- [ ] No `TypeError` when comparing datetimes across modules
