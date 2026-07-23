---
id: DOC-024
type: plan
status: active
phase: G
owner: james
tags: [phase-g, risk]
links: []
updated: 2026-07-22
---

# Phase G — Paper-to-Live Transition Plan

**Date:** 2026-05-06
**Status:** Decisions locked — implementation pending paper-trade prerequisites
**Roadmap link:** [/roadmap#paper-to-live](/roadmap#paper-to-live)

## Locked decisions (2026-05-06)

After reviewing the v1 draft of this plan, the four open questions
were settled as follows. These are the binding parameters for
implementation; the rest of the doc is updated to reflect them.

| # | Decision | Rationale |
|---|---|---|
| 1 | **Final live allocation: $200** | Deliberately small for a first live run. Strategy and infra are unproven at any scale; $200 limits damage on a bad surprise while still providing real-money signal. Can be raised later by adjusting `target_live_allocation` once Stage 4 has run for several months without incident. |
| 2 | **Losing weeks during paper trading ARE a graduation blocker** | Stricter than the v1 draft. Aligns with "guardrails preventing progress" being a *bug* (the system shouldn't lose money in low-stakes paper) rather than a virtue. A losing paper week means the strategy is wrong, not that the gates are too tight. |
| 3 | **Rollback = kill switch + manual unwind** (as designed) | Human-in-the-loop on rollback is correct. Auto-downgrade adds another autonomous decision surface during a stressful event; we'd rather fail conservative. |
| 4 | **No manual per-trade approval in Stage 1** | The point of automation is automation. Adding a human checkpoint per trade defeats the purpose and isn't sustainable. Stage 1's *bridge gate review* (after each stage's window) is the human-decision surface. |

## Summary

The transition from `ALPACA_PAPER=true` to live capital is the highest-risk
single change in the project. This document designs a *graduated* scale-up
that gives the system multiple intermediate checkpoints to fail safe at,
rather than flipping a binary switch.

**Target final allocation: $200.**

The path is **paper-trading-baseline → live-$20 → live-$50 → live-$100 →
live-$200**, with each stage gated on quantitative criteria measured over
a defined observation window. Failing any gate → roll back one stage and
diagnose, do not proceed.

## Prerequisites (must be met before Stage 1)

These are *blocking* — Phase G doesn't begin until all are green.

| # | Criterion | How to verify |
|---|---|---|
| 1 | **30+ executed paper trades** completed | `SELECT COUNT(*) FROM trades WHERE executed = TRUE AND timestamp > '2026-04-22';` ≥ 30 |
| 2 | **Win rate** of paper trades is ≥ 50% on a 1:1+ RR strategy, OR profit factor > 1.0 if RR varies | `/trades/summary` page → win rate column |
| 3 | **Max drawdown** in paper portfolio ≤ 15% | `/analytics` page → max DD card |
| 4 | **Zero losing weeks** in the paper-trade graduation window (decision #2 — stricter than the draft) | Compute weekly equity series from `/portfolio/snapshots`; any week with weekly P&L < 0 fails this gate |
| 5 | **No critical guardrail blocks** dominating the audit log | `/trades/block-stats` → no reason >20% of total |
| 6 | **30 consecutive cycles without backend errors** in `/errors` page | observation |
| 7 | **Live Alpaca account approved** (currently in review) | Alpaca dashboard shows "Live Trading" tab unlocked |
| 8 | **PDT compliance plan finalized** for the chosen capital level | At $200 the account is *far* under the $25k PDT threshold — `daily_order_limit` must be ≤ 3 to avoid 4-day-trade trigger |

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

### Stage 1 — Live at $20 (10% of $200)

- `ALPACA_PAPER=false`
- `MAX_TOTAL_INVESTED` = $20.
- `MAX_SINGLE_TRADE_SIZE` = $5 (caps single-position concentration at 25%
  of stage allocation; at $200 final, that's a $50 cap which is still tiny).
- Heavy reliance on **fractional shares** — at $5 per trade, almost
  everything will be fractional. Alpaca supports this on paper and live.
- Window: **2 calendar weeks**, minimum 5 executed trades (lowered from
  the draft's 10 because the small dollar size limits trade count;
  a $5 buy + a future $5 sell is 2 trades, so 5 trades = ~3 buys).
- **Bridge gate** (must hold throughout window):
  - Realized P&L vs. paper-baseline P&L over the same window: within ±50%
    (looser than draft's ±30% because tiny dollar amounts make absolute
    P&L noisy; a single $0.10 fill difference is large in % terms).
  - Zero unexpected `Execution error` blocks (would indicate broker
    integration regressions).
  - Drawdown ≤ 10% of allocated capital ($2 max loss in Stage 1).
  - Slippage check **dropped at this scale** — with $5 trades, slippage
    measurement is dominated by noise, not signal. Reintroduces at Stage 3.
  - **Zero losing weeks** in the Stage 1 window (consistent with the
    paper-trade graduation prerequisite).
- Failure → roll back to Stage 0 paper, diagnose, redo Stage 1 after fix.

### Stage 2 — Live at $50 (25% of $200)

- Triggered only if Stage 1 passed all bridge gates for the full 2 weeks.
- `MAX_TOTAL_INVESTED` = $50, `MAX_SINGLE_TRADE_SIZE` = $12.
- Window: **2 calendar weeks**, minimum 8 executed trades.
- Same bridge gates as Stage 1, plus:
  - Sharpe ratio > 0.3 over Stage 1 + Stage 2 combined window (lower
    threshold than draft's 0.5 because $50 is still a small sample).
  - Zero losing weeks.
- Failure → roll back to Stage 1.

### Stage 3 — Live at $100 (50% of $200)

- Triggered only if Stage 2 passed.
- `MAX_TOTAL_INVESTED` = $100, `MAX_SINGLE_TRADE_SIZE` = $25.
- Window: **3 calendar weeks**, minimum 12 executed trades.
- Same gates plus:
  - Profit factor > 1.0 over Stages 1+2+3 combined.
  - Slippage on executed orders < 0.3% per trade on average
    (reintroduced now that dollar amounts are large enough to measure
    meaningfully — $25 trade × 0.3% = $0.075 noise floor).
  - No losing weeks.
  - No more than 1 weekly drawdown > 4%.

### Stage 4 — Live at $200 (full target)

- Triggered only if Stage 3 passed.
- `MAX_TOTAL_INVESTED` = $200, `MAX_SINGLE_TRADE_SIZE` = $50.
- Steady state. No further graduation gates — this is "production trading"
  at the v1 target.
- Continue monitoring `/trades/block-stats`, `/analytics`, `/errors` weekly.
- If any week shows drawdown > 8% ($16 loss) or 3+ consecutive losing
  weeks: trigger the kill switch and re-evaluate.

### Future scale-up (post Stage 4)

If Stage 4 runs cleanly for **3 consecutive months** with positive P&L
and no rollback events, the user may *manually* raise
`target_live_allocation` (e.g., $200 → $500 → $1000 → …) in increments
of ≤ 2.5× per step. Each raise re-enters at Stage 4 of the new target;
graduation stages 1-3 are not re-run for raises. If the user wants to
make a larger jump (>2.5×), the full Phase G graduation cycle restarts.

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

## Decision points (resolved 2026-05-06)

| # | Question | Decision |
|---|---|---|
| 1 | Final target allocation? | **$200** |
| 2 | Are losing weeks during paper trading a graduation blocker? | **Yes** — losing weeks indicate the strategy is wrong, not that gates are too tight |
| 3 | Rollback procedure (kill switch + manual unwind vs. auto-downgrade)? | **Kill switch + manual unwind** (human in loop on rollback) |
| 4 | Manual per-trade approval in Stage 1? | **No** — defeats the point of automation; bridge-gate review at end of each window is the human checkpoint |

## Cross-references

- Roadmap entry: `/roadmap#paper-to-live` (Phase G)
- Predecessor: paper-trading milestone in `/todos` (id: paper-trade-30)
- Related: live Alpaca account approval (currently pending)
- Related: today's audit-log fixes (`integration-issues/zero-qty-trades-pollute-audit-log.md`)
  unblock the paper-trade pipeline, which gates this phase.
