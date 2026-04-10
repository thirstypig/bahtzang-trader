---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, quality, architecture]
dependencies: []
---

# Untyped Dicts Threaded Through Pipeline

## Problem Statement

The `decision` variable is a raw `dict` threaded through the entire pipeline. Key names like `decision.get("ticker")` can silently return `None` on typos. No IDE autocompletion, no compile-time checks.

**Found by:** Python reviewer, Architecture strategist (2 agents)

## Findings

- `backend/app/trade_executor.py`: passes `decision` as a raw `dict` through the pipeline
- `backend/app/claude_brain.py`: returns trade decisions as untyped dicts
- `backend/app/guardrails.py`: receives and inspects `decision` dict with string key access
- `decision.get("ticker")` and similar calls silently return `None` on key typos
- No IDE autocompletion or static analysis support for the decision structure
- A typo in a key name (e.g., `"tickr"` instead of `"ticker"`) would silently pass through

## Proposed Solutions

Create a `TradeDecision` dataclass or Pydantic model. Also type the return of `run_cycle`. ~30 lines:

1. Define a `TradeDecision` dataclass or Pydantic model with explicit fields (ticker, action, quantity, reasoning, etc.)
2. Update `claude_brain.py` to return a `TradeDecision` instance instead of a raw dict
3. Update `guardrails.py` and `trade_executor.py` to accept `TradeDecision` typed parameters
4. Add return type annotation to `run_cycle`

## Technical Details

**Affected files:** `backend/app/trade_executor.py`, `backend/app/claude_brain.py`, `backend/app/guardrails.py`

**Effort:** Medium (~30 lines)

## Acceptance Criteria

- [ ] A `TradeDecision` dataclass or Pydantic model is defined with explicit typed fields
- [ ] `claude_brain.py` returns a `TradeDecision` instance
- [ ] `guardrails.py` accepts a typed `TradeDecision` parameter
- [ ] `trade_executor.py` uses typed `TradeDecision` throughout the pipeline
- [ ] `run_cycle` has a return type annotation
- [ ] Key access typos are caught by type checkers and IDEs
- [ ] Existing tests pass with the new typed structure
