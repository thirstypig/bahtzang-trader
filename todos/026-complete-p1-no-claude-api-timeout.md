---
status: pending
priority: p1
issue_id: "026"
tags: [code-review, performance, reliability]
dependencies: []
---

# No Timeout on Claude API Call — Can Block 10 Minutes

## Problem Statement

The `client.messages.create()` call in `claude_brain.py` has no explicit timeout. The Anthropic SDK defaults to 600 seconds (10 minutes). During this time, the `_cycle_lock` mutex is held, blocking all other trading cycles and manual `/run` requests.

**Found by:** Performance oracle (CRITICAL)

## Findings

- `backend/app/claude_brain.py:134-139` — No `timeout` parameter on `messages.create()`
- Default timeout is 10 minutes per Anthropic SDK
- `_cycle_lock` in `trade_executor.py:23` is held during entire cycle
- Missed trading windows if API is degraded
- With 3x/5x frequency, one timeout cascades into multiple missed cycles

## Proposed Solutions

Add explicit 30-second timeout and graceful fallback:

```python
message = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": user_prompt}],
    timeout=30.0,
)
```

Add `except anthropic.APITimeoutError` handler returning a `hold` decision.

- **Effort:** Small (5 min)
- **Risk:** None

## Acceptance Criteria

- [ ] Claude API call has explicit 30-second timeout
- [ ] Timeout returns a "hold" decision with appropriate reasoning
- [ ] _cycle_lock is not held for more than ~60 seconds total

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-04-10 | Code review found issue | Performance oracle flagged |
