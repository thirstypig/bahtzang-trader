---
status: pending
priority: p2
issue_id: "012"
tags: [code-review, security, typescript]
dependencies: []
---

# Fetch API Headers Overwritten by Spread Operator

## Problem Statement

`{ headers, ...options }` -- if caller passes options with headers, the spread overwrites Authorization and Content-Type entirely. Future callers will silently lose auth.

**Found by:** TypeScript reviewer (1 agent)

## Findings

- `frontend/src/lib/api.ts` line 22: uses `{ headers, ...options }` pattern
- If a caller passes `options` that include a `headers` property, the spread operator overwrites the base `headers` (Authorization and Content-Type) entirely
- The Authorization header is silently lost, causing API calls to fail or proceed without authentication
- This is not currently triggered but is a latent bug waiting for any caller to pass custom headers

## Proposed Solutions

Merge headers: `{ ...options, headers: { ...headers, ...options?.headers } }`. 1 line:

1. Replace `{ headers, ...options }` with `{ ...options, headers: { ...headers, ...options?.headers } }` to properly merge base headers with caller-provided headers

## Technical Details

**Affected files:** `frontend/src/lib/api.ts` (line 22)

**Effort:** Small (1 line)

## Acceptance Criteria

- [ ] Base headers (Authorization, Content-Type) are preserved when callers pass custom headers
- [ ] Caller-provided headers can extend or override specific base headers
- [ ] The Authorization header is never silently dropped
- [ ] Existing API calls continue to work unchanged
