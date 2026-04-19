---
status: pending
priority: p2
issue_id: "094"
tags: [code-review, backend, type-safety]
dependencies: []
---

# CycleResult.quantity Typed as int but Is float

## Problem Statement

`CycleResult` TypedDict in `pipeline_types.py` types `quantity` as `int`, but after the fractional share support (commit 95bc538), quantity can be a `float` (e.g., `0.2500`). This is a type safety violation that could cause incorrect behavior in code that relies on the type annotation.

## Findings

- **Source:** Python Reviewer
- `pipeline_types.py:57` — `quantity: int`
- `executor.py:191` — `new_qty = round(max_affordable / price, 4)` produces float

## Proposed Solutions

Update the TypedDict: `quantity: int` → `quantity: float`

- **Effort:** Trivial
- **Risk:** None (just a type annotation fix)

## Acceptance Criteria

- [ ] `CycleResult.quantity` typed as `float`
- [ ] Any downstream code that assumes `int` is updated

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from Python reviewer | |
