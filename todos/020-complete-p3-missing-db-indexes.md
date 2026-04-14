---
status: complete
priority: p3
issue_id: "020"
tags: [code-review, performance, database]
dependencies: []
---

# Missing Database Indexes on Trades Table

## Problem Statement

The trades table has no indexes beyond the primary key. The guardrails daily count query scans the full table to count today's trades. The `GET /trades` endpoint does an unindexed `ORDER BY timestamp DESC`. As the trades table grows, both queries will degrade in performance.

**Found by:** Code review

## Findings

- `backend/app/models.py`: no index definitions on the trades model beyond the primary key
- Guardrails daily trade count query filters by timestamp range with no index support
- `GET /trades` sorts by `timestamp DESC` without an index, causing a full table sort
- Performance impact is negligible now but will grow linearly with trade volume

## Proposed Solutions

Add a composite index on `(timestamp, executed)` to support the guardrails query, and an index on `timestamp DESC` to support the trades listing endpoint.

## Technical Details

**Affected files:** `backend/app/models.py`

**Effort:** Small

## Acceptance Criteria

- [ ] A composite index on `(timestamp, executed)` is added to the trades model
- [ ] An index on `timestamp DESC` is added to support `ORDER BY` queries
- [ ] A database migration is created for the new indexes
- [ ] Existing queries benefit from the indexes without code changes
- [ ] No existing functionality is broken
