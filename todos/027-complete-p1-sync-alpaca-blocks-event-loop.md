---
status: complete
priority: p1
issue_id: "027"
tags: [code-review, performance, async]
dependencies: []
---

# Synchronous Alpaca SDK Calls Block Async Event Loop

## Problem Statement

The Alpaca `TradingClient` methods (`get_all_positions()`, `get_account()`, `submit_order()`) are synchronous HTTP calls called directly inside `async def` methods. This blocks the entire event loop, freezing ALL concurrent requests during broker API calls.

**Found by:** Performance oracle (CRITICAL), Architecture strategist (LOW)

## Findings

- `backend/app/brokers/alpaca.py:35,54,76` — Sync SDK calls inside `async def` methods
- `trade_executor.py:40-43` — `asyncio.gather()` on these calls provides zero concurrency benefit
- FastAPI's single event loop is blocked during each HTTP round trip
- Health checks, frontend API calls all freeze during broker calls

## Proposed Solutions

Wrap synchronous calls in `asyncio.to_thread()`:

```python
async def get_positions(self, account_id: str) -> list[dict]:
    client = _get_client()
    positions = await asyncio.to_thread(client.get_all_positions)
    return [...]
```

Apply to all three methods: `get_positions`, `get_account_balance`, `place_order`.

- **Effort:** Small (15 min)
- **Risk:** Low

## Acceptance Criteria

- [ ] All Alpaca SDK calls wrapped in `asyncio.to_thread()`
- [ ] `asyncio.gather()` in trade_executor actually runs calls concurrently
- [ ] Event loop not blocked during broker API calls

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-04-10 | Code review found issue | Performance oracle flagged |
