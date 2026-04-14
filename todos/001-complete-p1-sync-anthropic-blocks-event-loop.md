---
status: complete
priority: p1
issue_id: "001"
tags: [code-review, performance, reliability, critical]
dependencies: []
---

# Synchronous Anthropic Client Blocks the Async Event Loop

## Problem Statement

`anthropic.Anthropic` (synchronous client) is used inside `async def get_trade_decision()`. The call to `client.messages.create()` blocks the entire asyncio event loop for 2-30 seconds. During that time, health checks, all API requests, and the scheduler are frozen.

**Found by:** Python reviewer, Architecture strategist, Performance oracle, Pattern recognition (4 agents)

## Findings

- `backend/app/claude_brain.py` line 7: synchronous `anthropic.Anthropic` client is instantiated
- `backend/app/claude_brain.py` line 47: `client.messages.create()` is called inside an `async def`, blocking the event loop
- While the Anthropic API call is in-flight (2-30 seconds), the entire application is unresponsive
- Health checks will timeout, API requests queue up, and the scheduler cannot fire

## Proposed Solutions

Switch to `anthropic.AsyncAnthropic` and `await client.messages.create(...)`. This is a 2-line change:

1. Replace `anthropic.Anthropic` with `anthropic.AsyncAnthropic` on line 7
2. Replace `client.messages.create(...)` with `await client.messages.create(...)` on line 47

## Technical Details

**Affected files:** `backend/app/claude_brain.py` (lines 7, 47)

**Effort:** Small (2-line change)

## Acceptance Criteria

- [ ] `anthropic.Anthropic` is replaced with `anthropic.AsyncAnthropic`
- [ ] `client.messages.create()` is awaited with `await`
- [ ] The event loop remains responsive during Anthropic API calls
- [ ] Health checks and other endpoints respond while trade decisions are being generated
- [ ] Existing tests pass with the async client
