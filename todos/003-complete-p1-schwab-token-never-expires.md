---
status: complete
priority: p1
issue_id: "003"
tags: [code-review, security, reliability, critical]
dependencies: []
---

# Schwab OAuth Token Cached Forever With No Expiry Check

## Problem Statement

`_token_cache` stores the access token forever with no expiry check. OAuth tokens expire after ~30 minutes. After expiry, every Schwab API call fails with 401. `clear_token_cache()` exists but is never called anywhere. No retry-on-401 logic exists.

**Found by:** Security sentinel, Python reviewer, Architecture strategist, Performance oracle (4 agents)

## Findings

- `backend/app/schwab_client.py` lines 9-26: `_token_cache` stores the access token indefinitely
- OAuth access tokens from Schwab expire after approximately 30 minutes
- After token expiry, every Schwab API call silently fails with a 401 Unauthorized response
- `clear_token_cache()` is defined but never invoked anywhere in the codebase
- There is no retry-on-401 logic to recover from expired tokens
- This means the system works for ~30 minutes after startup, then all trading operations fail

## Proposed Solutions

Store `expires_at` alongside the token and add retry logic (~15 lines):

1. When caching the token, also store `expires_at = datetime.now() + timedelta(seconds=expires_in)`
2. Before returning a cached token, check if `datetime.now() >= expires_at` and refresh if expired
3. Add a buffer (e.g., refresh 60 seconds before actual expiry) to avoid edge cases
4. On any 401 response, clear the cache and retry the request once

## Technical Details

**Affected files:** `backend/app/schwab_client.py` (lines 9-26)

**Effort:** Small (~15 lines)

## Acceptance Criteria

- [ ] Token cache stores `expires_at` timestamp alongside the access token
- [ ] Cached tokens are validated for expiry before being returned
- [ ] Expired tokens trigger automatic refresh before API calls
- [ ] 401 responses from Schwab clear the cache and retry the request once
- [ ] `clear_token_cache()` is wired into the retry logic
- [ ] Token refresh includes a safety buffer before actual expiry
