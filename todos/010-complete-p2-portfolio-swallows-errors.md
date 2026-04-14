---
status: complete
priority: p2
issue_id: "010"
tags: [code-review, security, reliability]
dependencies: []
---

# Portfolio Endpoint Swallows Errors and Returns Fake Data

## Problem Statement

`/portfolio` catches all exceptions and returns fake zeroed-out data (`cash_available: 0, total_value: 0`). User sees $0 balance with no error indication. Trading bot could use zeroed data during a scheduled cycle.

**Found by:** Security sentinel, Python reviewer, Pattern recognition (3 agents)

## Findings

- `backend/app/main.py` lines 63-74: the `/portfolio` endpoint has a bare `except` that catches all exceptions
- On any error, it returns zeroed-out data (`cash_available: 0, total_value: 0`) instead of an error response
- The user sees a $0 balance with no indication that an error occurred
- The trading bot could consume zeroed portfolio data during a scheduled cycle, leading to incorrect trading decisions
- This masks connection issues, auth failures, and API errors that should be surfaced

## Proposed Solutions

Return HTTP 503 with error details so frontend shows error state. ~5 lines:

1. Replace the bare `except` with specific exception handling
2. Return an HTTP 503 (Service Unavailable) response with error details
3. Let the frontend display an error state instead of misleading $0 data

## Technical Details

**Affected files:** `backend/app/main.py` (lines 63-74)

**Effort:** Small (~5 lines)

## Acceptance Criteria

- [ ] The bare `except` is replaced with an HTTP 503 response containing error details
- [ ] The frontend receives an error status code and can display an error state
- [ ] Zeroed-out fake data is no longer returned on errors
- [ ] The trading bot does not consume fake portfolio data during scheduled cycles
- [ ] Connection issues, auth failures, and API errors are surfaced to the caller
