---
status: complete
priority: p2
issue_id: "035"
tags: [code-review, ai-prompting, data-accuracy]
dependencies: []
---

# Hardcoded Stale Yield/Ticker Data in GOAL_PROMPTS

## Problem Statement

`GOAL_PROMPTS` embeds specific yield percentages (`SCHD (3.2%)`, `JEPI (7.8%)`) and assumes certain tickers exist. These numbers are already stale — yields change quarterly. Claude has no live yield data to verify the constraints.

**Found by:** Python reviewer (P2)

## Findings

- `backend/app/claude_brain.py:46-98` — Hardcoded yields in prompt text
- `steady_income` goal says "Only buy stocks with yield > 3%" but Claude receives no yield data
- Claude may hallucinate yields based on outdated training data
- Yield percentages in prompt will drift from reality over time

## Proposed Solutions

### Option A: Strip specific yield numbers
Replace exact yields with relative instructions: "Focus on high-dividend stocks"

### Option B: Enrich market_data with yield data (Phase D)
Add dividend yield to the data pipeline so Claude can verify constraints

- **Effort:** Small (A) / Medium (B, future phase)
- **Risk:** Low
