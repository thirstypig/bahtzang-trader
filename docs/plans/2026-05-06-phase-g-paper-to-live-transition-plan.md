# Phase G — Paper-to-Live Transition Plan

**Date:** 2026-05-06
**Status:** Design only — implementation deferred until Phase G prerequisites land
**Roadmap link:** [/roadmap#paper-to-live](/roadmap#paper-to-live)

## Summary

The transition from `ALPACA_PAPER=true` to live capital is the highest-risk
single change in the project. This document designs a *graduated* scale-up
that gives the system multiple intermediate checkpoints to fail safe at,
rather than flipping a binary switch.

The path is **paper-trading-baseline → live-10% → live-25% → live-50% →
live-100%**, with each stage gated on quantitative criteria measured over
a defined observation window. Failing any gate → roll back one stage and
diagnose, do not proceed.

## Prerequisites (must be met before Stage 1)

These are *blocking* — Phase G doesn't begin until all are green.

| # | Criterion | How to verify |
|---|---|---|
| 1 | **30+ executed paper trades** completed | `SELECT COUNT(*) FROM trades WHERE executed = TRUE AND timestamp > '2026-04-22';` ≥ 30 |
| 2 | **Win rate** of paper trades is ≥ 50% on a 1:1+ RR strategy, OR profit factor > 1.0 if RR varies | `/trades/summary` page → win rate column |
| 3 | **Max drawdown** in paper portfolio ≤ 15% | `/analytics` page → max DD card |
| 4 | **No critical guardrail blocks** dominating the audit log | `/trades/block-stats` → no reason >20% of total |
| 5 | **30 consecutive cycles without backend errors** in `/errors` page | observation |
| 6 | **Live Alpaca account approved** (currently in review) | Alpaca dashboard shows "Live Trading" tab unlocked |
| 7 | **PDT compliance plan finalized** for the chosen capital level | If account < $25k, `daily_order_limit` set to ≤ 3 to avoid 4-day-trade trigger |

Failing any prerequisite extends paper trading. The ratio of paper-trade
success to "interesting things still happening" should approach 1.0
before live capital is at risk.

## Stages

### Stage 0 — Paper baseline (current)

- `ALPACA_PAPER=true`
- All capital is virtual.
- Window: until prerequisites are met. Currently estimated 30+ trading days
  given 1x/day cadence on the moderate risk preset.
- Goal: prove the strategy executes the rules consistently and the
  guardrails work as intended.

### Stage 1 — Live at 10% allocation

- `ALPACA_PAPER=false`
- `MAX_TOTAL_INVESTED` set to 10% of intended final allocation
  (e.g., if final target is $25k, Stage 1 caps at $2,500 invested).
- Window: **2 calendar weeks**, minimum 10 executed trades.
- **Bridge gate** (must hold throughout window):
  - Realized P&L vs. paper-baseline P&L over the same window: within ±30%
    (allows for some slippage but flags major divergence).
  - Zero unexpected `Execution error` blocks (would indicate broker
    integration regressions).
  - Drawdown ≤ 5% of allocated capital.
  - Slippage on executed orders < 0.2% per trade on average (compare
    expected fill price to actual).
- Failure → roll back to Stage 0 paper, diagnose, redo Stage 1 after fix.

### Stage 2 — Live at 25% allocation

- Triggered only if Stage 1 passed all bridge gates for the full 2 weeks.
- `MAX_TOTAL_INVESTED` raised to 25% of final.
- Window: **2 calendar weeks**, minimum 15 executed trades.
- Same bridge gates as Stage 1, plus:
  - Sharpe ratio > 0.5 over the Stage 1 + Stage 2 combined window
    (live data, not paper).
- Failure → roll back to Stage 1 (don't go all the way to paper unless
  Stage 1 also fails on rerun).

### Stage 3 — Live at 50% allocation

- Triggered only if Stage 2 passed.
- `MAX_TOTAL_INVESTED` raised to 50% of final.
- Window: **3 calendar weeks**, minimum 25 executed trades.
- Same gates plus:
  - Profit factor > 1.0 over Stages 1+2+3 combined.
  - No more than 1 weekly equity drawdown > 4%.

### Stage 4 — Live at 100%

- Triggered only if Stage 3 passed.
- `MAX_TOTAL_INVESTED` raised to full target.
- Steady state. No further graduation gates — this is "production trading."
- Continue monitoring `/trades/block-stats`, `/analytics`, `/errors` weekly.
- If any week shows drawdown > 8% or 3+ consecutive losing weeks: trigger
  the kill switch and re-evaluate.

## Rollback procedure (any stage)

1. **Activate kill switch** via /settings → all trading halts immediately
2. **Lower `MAX_TOTAL_INVESTED`** to previous stage's cap
3. **Manually unwind positions** that exceed the new cap (sell down to
   the lower target via the dashboard or directly via Alpaca)
4. **Wait until cash = stage cap, positions ≤ stage cap**
5. **Deactivate kill switch**, resume one stage lower

The Alpaca paper environment remains a valid "debug surface" — flip
`ALPACA_PAPER=true` temporarily to test changes that need real-world data
without risking capital.

## Observability — what to watch on each stage

The dashboard already surfaces most of this. To make graduation decisions,
check daily:

| Metric | Page | Threshold |
|---|---|---|
| Cumulative P&L | `/analytics` | Must trend ≥ paper baseline ± 30% |
| Sharpe (rolling 30d) | `/analytics` | > 0.3 by Stage 2 end, > 0.5 by Stage 3 |
| Max drawdown | `/analytics` | < stage-specific threshold |
| Block rate | `/trades/block-stats` | < 20% per reason |
| Error rate | `/errors` | 0 critical errors per week |
| Trade execution latency | Railway logs / Alpaca API | < 2s p50 |

A *bahtzang-graduation-status* admin page (Phase G+) could show all of
these at a glance with stage-specific go/no-go indicators. Out of scope
for Phase G v1.

## Implementation work breakdown (when prerequisites are met)

This is the engineering plan that gets built once paper trading is
greenlit. Roughly ordered by dependency:

1. **Add `target_live_allocation` setting** to GuardrailsConfig
   (separate from `max_total_invested` — the latter clamps each stage,
   the former is the eventual full target). One DB column, one form
   field on /settings.
2. **Add a `live_stage` enum** to GuardrailsConfig with stages
   `paper | live_10 | live_25 | live_50 | live_100`. Default `paper`.
   Stage transitions are manual (require explicit /settings change) —
   never automatic — so the human is always in the loop.
3. **Stage-aware position sizing**: when `live_stage != paper`,
   `effective_max_invested = target_live_allocation * stage_pct`.
   Pass into Claude's USAGE/HEADROOM block so AI plans within the
   stage's cap.
4. **Stage transition audit log**: every `live_stage` change writes
   to `guardrails_audit` table with old/new value, timestamp, user.
5. **Frontend: stage indicator banner** on the dashboard. Color-coded.
   Shows current stage, days-in-stage, gate-progress (e.g., "12/14 days,
   8/10 trades — green/yellow/red on each metric").
6. **Migration script**: when current users adopt this, default to
   `paper` and require explicit upgrade.
7. **Documentation**: update CLAUDE.md trading pipeline section,
   README, /docs page.

Estimated: 3–5 days of focused work once prerequisites are met.

## What this design intentionally does NOT do

- **No automatic stage transitions.** The graduation is human-decision-only.
  An automated graduation script would be tempting but risky — too many
  ways for bad data or a brief lull in losses to fool a check into
  promoting prematurely.
- **No automatic rollback either.** A flat-week or single-loss-trade
  shouldn't trigger an unwind — only the kill switch does, and only via
  human or circuit-breaker action.
- **No "stage skipping".** Even if Stage 1 wildly outperforms, Stage 2 and 3
  must each run their full window. The gates are about *time-in-state*
  evidence as much as P&L.
- **No leveraged products in any stage.** Same equity universe as the
  paper baseline. Adding leverage (futures, margin, options) would
  invalidate the paper-baseline comparison.

## Decision points before implementation

These need user input before the work starts:

1. **What is the final target allocation?** ($1k → $25k → $100k changes
   the absolute thresholds for everything else.)
2. **Are losing weeks during paper trading a graduation blocker?** The
   prerequisite says "win rate ≥ 50% OR PF > 1." Some users might want
   stricter (e.g., zero losing weeks).
3. **Is the rollback procedure acceptable?** Currently designed as
   "kill switch + manual unwind" — alternative is automatic stage
   downgrade on threshold breach, which is more aggressive.
4. **Should Stage 1 require monitoring presence?** I.e., during the
   first 2 weeks of live capital, should a person manually approve each
   trade decision before execution? Adds safety, eliminates automation.

## Cross-references

- Roadmap entry: `/roadmap#paper-to-live` (Phase G)
- Predecessor: paper-trading milestone in `/todos` (id: paper-trade-30)
- Related: live Alpaca account approval (currently pending)
- Related: today's audit-log fixes (`integration-issues/zero-qty-trades-pollute-audit-log.md`)
  unblock the paper-trade pipeline, which gates this phase.
