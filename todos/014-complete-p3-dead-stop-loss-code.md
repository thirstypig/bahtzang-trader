---
status: pending
priority: p3
issue_id: "014"
tags: [code-review, quality]
dependencies: []
---

# Dead Stop-Loss Guardrail Code

## Problem Statement

The stop-loss check in `guardrails.py` uses `decision.get("loss_pct", 0)` but nothing in the codebase ever sets `loss_pct`. The check always evaluates to `0 > 0.05` which is `False`. The stop-loss guardrail never fires.

**Found by:** Code review

## Findings

- `backend/app/guardrails.py` lines 82-84: stop-loss check reads `loss_pct` from the decision dict
- No code path in the codebase ever populates `loss_pct` in the decision
- The default value of `0` means the comparison `0 > 0.05` is always False
- The stop-loss guardrail is effectively dead code that provides a false sense of safety

## Proposed Solutions

Either compute `loss_pct` from the entry price and current price so the guardrail actually works, or remove the dead code to avoid misleading developers into thinking stop-loss protection exists.

## Technical Details

**Affected files:** `backend/app/guardrails.py` (lines 82-84)

**Effort:** Small

## Acceptance Criteria

- [ ] The stop-loss guardrail either fires correctly based on real loss data or is removed
- [ ] If kept, `loss_pct` is computed from entry price and current market price
- [ ] If removed, any references to stop-loss in comments or docs are cleaned up
