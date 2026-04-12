---
status: pending
priority: p2
issue_id: "037"
tags: [code-review, security, validation]
dependencies: ["021"]
---

# No Schema Validation on Loaded Guardrails File

## Problem Statement

`load_guardrails()` reads whatever is in `guardrails.json` without validating types or ranges. A tampered file could set `max_total_invested: 999999999` or `min_confidence: 0.01`, bypassing intended limits.

**Found by:** Security sentinel (M4 MEDIUM)

## Findings

- `backend/app/guardrails.py:112-126` — `json.load()` with `setdefault()` but no validation
- Pydantic `GuardrailsUpdate` only validates API input, not loaded file contents
- Arbitrary values in JSON file are used by `check_guardrails()` without complaint

## Proposed Solutions

Validate loaded config against Pydantic model:
```python
def load_guardrails() -> dict:
    raw = json.load(f)
    validated = GuardrailsUpdate(**raw)
    return validated.model_dump()
```

- **Effort:** Small
- **Risk:** Low (will be superseded when guardrails move to DB)
