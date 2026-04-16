---
status: complete
priority: p2
issue_id: "069"
tags: [code-review, architecture, plans, concurrency]
dependencies: []
---

# Two separate execution locks — plan + legacy cycles can collide

## Problem Statement
`_execution_lock` in `plans/executor.py` and `_cycle_lock` in `trade_executor.py` are independent `asyncio.Lock()` instances. Both protect Alpaca order placement, but they don't coordinate. A plan cycle + legacy `/run` endpoint could execute orders simultaneously against the same Alpaca account, causing unexpected state.

## Findings
- `backend/app/plans/executor.py:23` — `_execution_lock = asyncio.Lock()`
- `backend/app/trade_executor.py:26` — `_cycle_lock = asyncio.Lock()`

## Proposed Solution
Move the lock to `app/brokers/alpaca.py` as a broker-level lock:
```python
# alpaca.py
_broker_lock = asyncio.Lock()

async def place_order(...):
    async with _broker_lock:
        ...
```

Both executors then benefit automatically without knowing about each other.

## Acceptance Criteria
- [ ] Single shared lock at broker level
- [ ] Plan cycle + legacy run can't interleave orders
