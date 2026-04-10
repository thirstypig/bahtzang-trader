---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, performance]
dependencies: []
---

# New HTTP Client Created Per Request

## Problem Statement

Every API call creates a new `httpx.AsyncClient`, meaning new TCP connection + TLS handshake each time. Adds ~50-150ms overhead per request.

**Found by:** Performance oracle, Python reviewer, Pattern recognition (3 agents)

## Findings

- `backend/app/schwab_client.py`: 4 instances of creating a new `httpx.AsyncClient` per call
- `backend/app/market_data.py`: 2 instances of creating a new `httpx.AsyncClient` per call
- Each new client triggers a fresh TCP connection and TLS handshake
- Adds ~50-150ms overhead per request, compounding across multiple calls in a pipeline cycle

## Proposed Solutions

Create module-level shared clients. ~15 lines:

1. Create a shared `httpx.AsyncClient` instance at the module level (or via a singleton pattern)
2. Replace all 6 instances of per-request client creation with the shared client
3. Ensure the shared client is properly configured with appropriate timeouts and connection pool settings

## Technical Details

**Affected files:** `backend/app/schwab_client.py` (4 instances), `backend/app/market_data.py` (2 instances)

**Effort:** Small (~15 lines)

## Acceptance Criteria

- [ ] A shared `httpx.AsyncClient` is created at module level or via a singleton
- [ ] All 6 instances of per-request client creation are replaced with the shared client
- [ ] Connection pooling and keep-alive are utilized across requests
- [ ] Appropriate timeouts are configured on the shared client
- [ ] Per-request overhead is reduced by ~50-150ms per call
