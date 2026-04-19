---
status: pending
priority: p2
issue_id: "097"
tags: [code-review, backend, plans, ux]
dependencies: []
---

# PlanUpdate Cannot Null Out target_amount / target_date

## Problem Statement

`PlanUpdate` uses `model_dump(exclude_none=True)` which strips `None` values. Since `target_amount` and `target_date` default to `None`, a user can never clear a previously-set target. Once a target date is set, it's permanent.

## Findings

- **Source:** Python Reviewer
- `routes.py:48-50` — defaults are `None`, indistinguishable from "not provided"
- `routes.py:258` — `model_dump(exclude_none=True)` strips `None`

## Proposed Solutions

Use `model_dump(exclude_unset=True)` instead of `exclude_none=True`. This preserves explicitly-sent `null` values while still ignoring fields the client didn't include.

- **Effort:** Trivial — one word change
- **Risk:** Low

## Acceptance Criteria

- [ ] User can PATCH a plan with `target_amount: null` to clear the target
- [ ] Fields not included in the PATCH request are still excluded

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from Python reviewer | |
