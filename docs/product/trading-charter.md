---
id: DOC-054
type: guide
status: draft
phase: null
owner: james
tags: [risk, portfolios, strategies, phase-g]
links: [DOC-053, PRD-002, DOC-002]
updated: 2026-10-19
---

# Trading charter

The rules every portfolio runs under. **Approved 2026-10-19.** Nothing here is built yet;
✅ = decided, ❓ = still open.

## 1. Goal

- ✅ **Beat buy-and-hold SPY, after all costs.** Costs = price spread, fees, the Claude API
  bill and estimated tax. Making money while trailing SPY counts as a loss.
- ✅ **Stocks only.** US-listed stocks plus SPY. No crypto, forex, options, leverage,
  margin or short selling.
- ✅ Paper money only until a portfolio passes the gate in section 7.

## 2. How the money is split

| Part | Share | Holds | Decided by |
|---|---|---|---|
| Core | 80% | ✅ SPY only, for now. It doubles as the yardstick | Buy and hold |
| Pool A: fast movers | ~3.3% × 2 | Listed stocks, price ≥ $5, ≥ $10M traded per day | Claude / simple rules |
| Pool B: cheap listed | ~3.3% × 2 | Listed stocks, price $1–5, ≥ $1M traded per day | Claude / simple rules |
| Pool C: OTC penny | ~3.3% × 2 | OTC stocks that Alpaca allows (309 today) | Claude / simple rules |

✅ Each pool runs twice on the same stock list: once with Claude choosing, once with a simple
rule. Same money, same safety limits. The only difference is who picks.

⚠️ **Pool C's paper results will look better than reality**, because paper fills ignore wide
spreads and thin trading. Reports label it that way.

## 3. Safety limits ✅ (all enforced in code, none by asking Claude)

| Rule | Limit |
|---|---|
| Stop-loss on every buy | A real stop order at Alpaca, placed with the buy (2 × the stock's typical daily move) |
| Risk per trade | A stopped-out trade loses ≤ 1% of the portfolio |
| Biggest single position | ≤ 20% of the portfolio |
| Max holdings at once | 8 |
| New buys per day | ≤ 2 per portfolio |
| Daily loss halt | Down 3% in a day → no new buys until tomorrow |
| Weekly loss halt | Down 6% in a week → no new buys until next week |
| Hard stop | Down 15% from start → portfolio switched off, Slack alert |
| Selling | Always allowed. The cooldown applies to buys only |
| Every run path | Limits apply to scheduled runs **and** the "Run Now" button |

Any automatic halt posts to Slack. Nothing pauses silently.

## 4. Costs

- ✅ Alpaca charges no commission on stock trades. Small regulatory fees apply on sells.
- Every trade records an **estimated spread cost** (half the bid-ask gap, each side).
- The **Claude API cost** is recorded per run and charged to the portfolio that used it.
- **Estimated tax:** ✅ 24% on short-term gains (held under a year).
- The backtester gets the same cost model, so backtests and live results are comparable.

## 5. Weekly report (Fridays after the close)

For each portfolio, and the account overall:
- Return vs SPY, **before and after costs**
- Trades, win rate, average win vs average loss
- Costs: spread, fees, API, estimated tax
- Every time a safety limit fired
- A short "what we learned / what we'd change" note

## 6. How we learn

- Claude has no memory between days. Learning is a process **we** run.
- Weekly review of the report. **Change at most one rule per portfolio per review**, and log
  it in the experiment log (EXP-###) with the reason.
- No rule changes in the middle of a week.

## 7. Pass / fail

- ✅ **Graduation gate (replaces "zero losing weeks", approved 2026-10-19):** after ≥ 12 weeks
  and ≥ 30 trades, **beat SPY after costs**, worst drop from peak ≤ 15%, and no single week
  worse than -5%. Passing earns the $200 live trial, not proof of an edge. (Why: SPY itself
  loses roughly 4 weeks in 10, so "zero losing weeks" mostly measured luck.)
- **Cut rule:** a pool that trails SPY by more than 10 points after 12 weeks is switched off.

## 8. Build order (before any portfolio is switched on)

1. Real stop orders: wire in the risk engine. First, one tiny test order to confirm Alpaca accepts it.
2. Let sells through the cooldown.
3. Enforce the section 3 limits in code. Apply them to "Run Now" too.
4. Cost tracking (spread, API, tax estimate) and the weekly report.
5. Switch off crypto and the "behind target, take more risk" prompt.
6. Stock pools A/B/C and the simple-rule strategy for them.
7. Create the core and the 6 experiment portfolios.

## Open decisions for James

None. All decided 2026-10-19.
