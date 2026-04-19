---
status: complete
priority: p3
issue_id: "088"
tags: [code-review, plans, performance]
dependencies: []
---

# Per-plan lock held across Claude API call (5-30s)

## Problem Statement
The per-plan lock wraps the entire `_run_plan_cycle_locked` body including the Claude API call (2-5 seconds) and subsequent trade executions. If a manual `/run` collides with a scheduled cycle, one blocks the other for that full duration.

Low impact in practice (single-user app, rare collisions), but narrowing the lock would be cleaner.

## Findings
- `backend/app/plans/executor.py:82-109` — lock held across Claude call

## Proposed Solution
Narrow the lock to only wrap DB mutations:
1. Read virtual_cash WITHOUT lock
2. Make Claude call WITHOUT lock
3. Acquire lock
4. Re-read plan, check virtual_cash hasn't changed
5. Execute trades + commit under lock
6. Release lock

Or accept the current behavior — the existing behavior is correct, just not optimal. Defer unless collisions become a problem.

## Resolution
Accepted as-is. The broad lock is correct and prevents double-spending. Narrowing adds complexity (optimistic check + retry logic) for a collision window that rarely occurs in a single-user app. Revisit if multi-user or high-frequency plans become a requirement.

## Acceptance Criteria
- [x] Decide: accepted current behavior (documented)
