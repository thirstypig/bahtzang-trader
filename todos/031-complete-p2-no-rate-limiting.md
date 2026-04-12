---
status: pending
priority: p2
issue_id: "031"
tags: [code-review, security, api]
dependencies: []
---

# No Rate Limiting on Any Endpoint

## Problem Statement

No rate limiting exists. `POST /run` triggers expensive API calls to Alpaca, Alpha Vantage, and Anthropic. A compromised token or rapid requests could exhaust API quotas and execute excessive trades.

**Found by:** Security sentinel (H4 HIGH)

## Findings

- `backend/app/main.py` — No rate limiting middleware configured
- `POST /run` triggers full trading cycle with external API calls
- `_cycle_lock` serializes but doesn't limit frequency
- Daily order limit guardrail only counts executed trades, not cycle attempts
- Anthropic API quota and Alpaca rate limits (200 req/min paper) at risk

## Proposed Solutions

Add `slowapi` rate limiting:
- `POST /run`: 1 request per 30 seconds
- All other endpoints: 60 requests per minute

- **Effort:** Small (~30 lines)
- **Risk:** Low
