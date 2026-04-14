---
status: complete
priority: p3
issue_id: "019"
tags: [code-review, bug, analytics]
dependencies: []
---

# Analytics "Win Rate" Metric Is Misleading

## Problem Statement

The "Win Rate" displayed on the analytics page filters trades by `confidence > 0.6`, not by whether trades actually made money. The label says "Win Rate" but the metric is really "High Confidence Rate". This is misleading and could cause users to make decisions based on incorrect performance data.

**Found by:** Code review

## Findings

- `frontend/src/app/analytics/page.tsx` line 22: win rate calculation filters by confidence threshold, not by actual trade outcomes
- The metric does not compare entry price vs. exit price or any profit/loss data
- A user reading "Win Rate: 72%" would assume 72% of trades were profitable, which is not what the number represents

## Proposed Solutions

Either rename the metric to "High Confidence Rate" to accurately describe what it measures, or compute the actual win rate from price data (entry price vs. exit price or current price) to show real trade performance.

## Technical Details

**Affected files:** `frontend/src/app/analytics/page.tsx` (line 22)

**Effort:** Small

## Acceptance Criteria

- [ ] The metric label accurately describes what is being calculated
- [ ] If showing actual win rate: computation uses real profit/loss data from trades
- [ ] If renaming: label changed to "High Confidence Rate" or similar accurate name
- [ ] Users are not misled about trading performance
