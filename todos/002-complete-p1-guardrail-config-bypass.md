---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, security, guardrails, critical]
dependencies: []
---

# Guardrail Configuration Bypass via Unvalidated POST /guardrails

## Problem Statement

`POST /guardrails` accepts a raw `dict` with zero validation. An attacker (or bug) can: set `kill_switch` to false, set `max_total_invested` to $999M, inject arbitrary keys, or set values to negative numbers. For a system controlling real money, this is a safety hazard.

**Found by:** Security sentinel, Python reviewer (2 agents)

## Findings

- `backend/app/main.py` line 112: the `/guardrails` POST endpoint accepts an unvalidated `dict`
- No type checking, range validation, or field whitelisting is performed
- The `kill_switch` can be disabled through this endpoint, bypassing any intended kill switch controls
- Arbitrary keys can be injected into the guardrails configuration
- Numeric values can be set to negative numbers or unreasonably large amounts

## Proposed Solutions

Create a Pydantic model with validated fields (~20 lines):

1. Define a `GuardrailsUpdate` Pydantic model with explicit fields and validators (e.g., `gt=0`, `le=limits`)
2. Omit `kill_switch` from the update model -- it should only be set via `/killswitch`
3. Replace the raw `dict` parameter with the Pydantic model in the endpoint signature
4. FastAPI will automatically validate and reject malformed requests

## Technical Details

**Affected files:** `backend/app/main.py` (line 112)

**Effort:** Small (~20 lines)

## Acceptance Criteria

- [ ] A Pydantic model is created for guardrail updates with validated fields
- [ ] `kill_switch` cannot be modified through `POST /guardrails`
- [ ] Numeric fields have reasonable upper and lower bounds (e.g., `max_total_invested` has a sane ceiling)
- [ ] Arbitrary/unknown keys are rejected
- [ ] Negative values for monetary fields are rejected
- [ ] Invalid requests return clear 422 validation errors
