---
status: complete
priority: p1
issue_id: "005"
tags: [code-review, security, critical]
dependencies: []
---

# No Rate Limiting on Any Endpoint

## Problem Statement

No rate limiting exists anywhere. `/run` triggers a full trading cycle calling Schwab, Alpha Vantage, and Anthropic APIs. Spam clicking or a compromised token can: execute hundreds of trades, exhaust Anthropic quota ($$), hit Alpha Vantage rate limits, and trigger brokerage account locks.

**Found by:** Security sentinel

## Findings

- `backend/app/main.py` (all endpoints): no rate limiting middleware or decorators are present
- The `/run` endpoint triggers a complete trading cycle that calls multiple external APIs (Schwab, Alpha Vantage, Anthropic)
- Each `/run` invocation costs real money via Anthropic API usage and potentially executes real trades
- Without rate limiting, a compromised API token or accidental rapid requests can:
  - Execute hundreds of unintended trades on the brokerage account
  - Exhaust the Anthropic API quota, incurring significant costs
  - Hit Alpha Vantage rate limits, causing data retrieval failures
  - Trigger Schwab account locks due to suspicious activity
- There is no protection against denial-of-service attacks on any endpoint

## Proposed Solutions

Add `slowapi` rate limiting (~30 lines):

1. Install `slowapi` package
2. Configure a `Limiter` instance with appropriate defaults
3. Apply rate limits to endpoints:
   - `/run`: max 1 request per 30 seconds (trading cycle is expensive and slow)
   - Other endpoints: 60 requests per minute
4. Add proper error responses (429 Too Many Requests) with `Retry-After` headers

## Technical Details

**Affected files:** `backend/app/main.py` (all endpoints)

**Effort:** Small (~30 lines)

## Acceptance Criteria

- [ ] `slowapi` (or equivalent) is installed and configured
- [ ] `/run` endpoint is rate-limited to max 1 request per 30 seconds
- [ ] Other endpoints are rate-limited to 60 requests per minute
- [ ] Rate limit exceeded responses return 429 status with `Retry-After` header
- [ ] Rate limiting is based on client IP or API key
- [ ] Rate limit configuration is adjustable without code changes (environment variables)
