---
status: pending
priority: p1
issue_id: "091"
tags: [code-review, frontend, plans, reliability]
dependencies: []
---

# runPlan 15s Timeout Too Short for Claude API Calls

## Problem Statement

The `runPlan()` API call uses the default `AbortSignal.timeout(15000)` from `fetchAPI`. A plan run involves a Claude AI API call (up to 30s) plus broker operations. If the total exceeds 15s, the frontend shows an error even though the trade may have executed successfully on the backend.

**Why it matters:** User sees "Error" while a real-money trade actually went through. This causes confusion and could lead to duplicate manual runs.

## Findings

- **Source:** Performance Oracle
- `api.ts:39` — default `AbortSignal.timeout(15000)` on all API calls
- `api.ts:329-331` — `runPlan` uses `fetchAPI` without overriding the signal
- Backend Claude call timeout is 30s; broker call adds more time

## Proposed Solutions

Pass a longer timeout for the `runPlan` call:
```typescript
export async function runPlan(id: number): Promise<CycleResult> {
  return fetchAPI<CycleResult>(`/plans/${id}/run`, {
    method: "POST",
    signal: AbortSignal.timeout(45000),
  });
}
```

- **Effort:** Trivial — one line
- **Risk:** None

## Acceptance Criteria

- [ ] `runPlan` uses a 45s timeout instead of 15s
- [ ] User does not see false error messages during slow Claude calls

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from performance oracle review | |
