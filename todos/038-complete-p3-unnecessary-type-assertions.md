---
status: complete
priority: p3
issue_id: "038"
tags: [code-review, frontend, typescript]
dependencies: []
---

# Unnecessary Type Assertions Bypass Type Checking

## Problem Statement

Every `handleUpdate` call uses `as Partial<Guardrails>` which is redundant (object literals already satisfy the type) and masks potential type errors.

**Found by:** TypeScript reviewer (P2)

## Findings

- `frontend/src/app/settings/page.tsx:195,232,260` — `as Partial<Guardrails>` casts
- Object literals already satisfy `Partial<Guardrails>` due to typed `goal.id`, `freq.id`, `profile.id`
- Removes type safety — if a field name is wrong, compiler won't catch it

## Fix

Remove `as Partial<Guardrails>` from all `handleUpdate()` calls.
