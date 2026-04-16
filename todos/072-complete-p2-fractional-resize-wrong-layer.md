---
status: complete
priority: p2
issue_id: "072"
tags: [code-review, architecture, plans]
dependencies: []
---

# Fractional resize silently overrides Claude's decision — wrong layer

## Problem Statement
The new fractional auto-resize in `plans/executor.py` modifies Claude's `quantity` without updating the reasoning. The trade log shows Claude said "buy 1 share" but the actual quantity was 0.25 — audit trail corrupted. Also mixes concerns: the executor is now making sizing decisions.

## Findings
- `backend/app/plans/executor.py:150-161` — silently modifies `decision["quantity"]`

## Proposed Solution
Two options:

**Option A** (simpler): Update reasoning when resizing:
```python
decision["reasoning"] += f" [Auto-resized from {original_qty} to {new_qty} to fit ${remaining_cash:.2f} cash]"
```

**Option B** (cleaner): Tell Claude the exact cash in the prompt so it sizes correctly itself, remove the auto-resize. Already partially done via prompt update but kept the override as belt-and-suspenders.

Recommend Option A for clarity + keeping safety net.

## Acceptance Criteria
- [ ] Reasoning reflects the actual quantity used
- [ ] Audit trail shows resize happened
