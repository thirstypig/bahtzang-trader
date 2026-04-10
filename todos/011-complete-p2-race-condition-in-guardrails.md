---
status: pending
priority: p2
issue_id: "011"
tags: [code-review, security]
dependencies: []
---

# Race Condition in Guardrail Check and Order Execution

## Problem Statement

Guardrail check and order execution are not atomic. Two concurrent `/run` requests could both pass the daily trade limit check and both execute, exceeding the limit.

**Found by:** Security sentinel (1 agent)

## Findings

- `backend/app/trade_executor.py` lines 53-69: the guardrail check and order execution are separate, non-atomic steps
- Two concurrent `/run` requests can both pass the daily trade limit check simultaneously
- Both requests then execute their trades, exceeding the daily trade limit
- This is a classic TOCTOU (time-of-check to time-of-use) race condition
- The window is small but exploitable, especially with automated requests

## Proposed Solutions

Add `asyncio.Lock()` around `run_cycle`. ~5 lines:

1. Create a module-level `asyncio.Lock()` instance
2. Wrap the guardrail check and order execution in `async with lock:` to make them atomic
3. Concurrent requests will be serialized through the lock

## Technical Details

**Affected files:** `backend/app/trade_executor.py` (lines 53-69)

**Effort:** Small (~5 lines)

## Acceptance Criteria

- [ ] An `asyncio.Lock()` is created to guard the guardrail-check-to-execution sequence
- [ ] The guardrail check and order execution are atomic (cannot be interleaved)
- [ ] Concurrent `/run` requests are serialized through the lock
- [ ] The daily trade limit cannot be exceeded by concurrent requests
- [ ] Lock does not introduce deadlocks or excessive contention
