---
id: DOC-054
type: guide
status: active
phase: null
owner: james
tags: [risk, portfolios, strategies, phase-g]
links: [DOC-053, PRD-002, DOC-002]
updated: 2026-11-09
---

# Trading charter

The rules the experiment runs under. **Simplified 2026-11-09** — two strategies, one
yardstick. (Replaces the 2026-10-19 version with an 80% SPY core and three stock pools:
too many moving parts for one question.)

## 1. The question

**Can Claude pick stocks well enough to beat simply holding SPY, after all costs?**

- Making money while trailing SPY counts as a loss.
- Costs = fees on sales, the Claude API bill, and estimated tax (24% of net short-term
  gains). The bid-ask spread is recorded too, but paper fills already happen at the
  bid/ask, so it's already in the result.
- Stocks only: US-listed stocks. No crypto, forex, options, leverage, margin or short selling.
- Paper money only until a strategy passes the gate in section 5.

## 2. The two strategies

Both get **$10,000 of paper money**, pick from the **same daily shortlist** (the stocks the
screener ranks highest among large and mid-size US companies — liquid, no penny stocks),
and are judged the same way: **beat SPY after costs**. Claude makes the picks in both;
what differs is the style Claude is asked for and the bet sizes the code enforces.

### Conservative — "the steady one"

- **What it does:** buys large, stable companies and mostly holds them. Trades only when
  Claude sees a clear, high-confidence opportunity.
- **Bet size (enforced in code):** a stopped-out trade loses at most **0.5%** of the
  portfolio; no single stock is more than **10%** of it.
- **What to expect:** smaller swings, fewer trades. It wins if careful, steady picks beat SPY.
- **Watch for:** it may trade too rarely to reach 30 trades in 12 weeks. If so, loosen how
  picky it is — at a weekly review, never mid-week.

### Aggressive — "the hunter"

- **What it does:** goes after the stocks with the strongest momentum; comfortable with
  bigger price swings.
- **Bet size (enforced in code):** a stopped-out trade loses at most **1%** of the
  portfolio; no single stock is more than **20%** of it.
- **What to expect:** bigger swings, more trades. It wins if riding strong trends beats SPY.

**The yardstick is SPY's price** — no SPY portfolio is needed; the weekly report reads it.

## 3. Safety limits (both strategies; enforced in code, never by asking Claude)

| Rule | Limit |
|---|---|
| Stop-loss on every buy | A real stop order at Alpaca, placed with the buy (2 × the stock's typical daily move) |
| Risk per trade / biggest position | Per strategy — see section 2 |
| Max holdings at once | 8 |
| New buys per day | ≤ 2 |
| Daily loss halt | Down 3% in a day → no new buys until tomorrow |
| Weekly loss halt | Down 6% in a week → no new buys until next week |
| Hard stop | Down 15% from start → strategy switched off, Slack alert |
| Selling | Always allowed |

These apply to scheduled runs and the "Run Now" button. Any automatic halt posts to Slack.

## 4. Weekly report (Fridays after the close, on the Reports page)

For each strategy: return vs SPY before and after costs, trades, wins and losses, costs,
every safety limit that fired, and a draft note from Claude. **Change at most one rule per
strategy per review**, never mid-week, and log it in the experiment log (EXP-###) with the
reason.

## 5. Pass / fail (per strategy)

After **≥ 12 weeks and ≥ 30 trades**: beat SPY after costs, worst drop from peak ≤ 15%,
and no single week worse than -5%. Passing earns the $200 live trial (Phase G), not proof
of an edge.

## 6. Status

Built (PRs #46–#51 + this one): stops at Alpaca, safety limits, sells always allowed, cost
tracking, weekly report, crypto and target-pressure prompt off, per-strategy bet sizes.
**Running since 2026-11-09:** Conservative (portfolio id 7) and Aggressive (id 8), created by
`backend/scripts/create_conservative_aggressive.sql`. First buys 2026-11-10; the 12-week clock
starts then (earliest pass review: early February 2027).
