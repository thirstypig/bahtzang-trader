---
status: complete
priority: p2
issue_id: "029"
tags: [code-review, ai-prompting, claude-brain]
dependencies: []
---

# Conflicting Risk/Goal Instructions Sent to Claude

## Problem Statement

Users can combine contradictory settings: `risk_profile=aggressive` ("confidence above 45%") with `trading_goal=capital_preservation` ("80% confidence minimum"). Both are sent to Claude simultaneously with no precedence rule.

**Found by:** Python reviewer (P2)

## Findings

- `backend/app/claude_brain.py:112-113` — Both `risk_instruction` and `goal_instruction` sent in same prompt
- Aggressive risk: "confidence above 45%" vs Capital Preservation goal: "80% confidence minimum"
- Claude must arbitrarily pick one instruction — unpredictable behavior
- `TRADING_GOALS` defines `recommended_risk` per goal but it's never enforced

## Proposed Solutions

### Option A: Add precedence rule to SYSTEM_PROMPT
```
"When GOAL and RISK instructions conflict, GOAL takes precedence."
```

### Option B: Warn/auto-correct incompatible combinations
- When goal is selected, auto-set recommended risk profile
- Show warning in UI if user overrides to an incompatible combination

- **Effort:** Small (Option A) / Medium (Option B)
- **Risk:** Low
