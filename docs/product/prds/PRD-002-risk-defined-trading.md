---
id: PRD-002
type: prd
status: active
phase: G
owner: james
tags: [risk, trading-pipeline, portfolios, phase-g]
links: [PRD-001, EXP-002, DOC-017]
updated: 2026-07-22
---

# PRD-002 — Risk-defined trading

**Status: planned → building.** Design locked in the 2026-07-22 brainstorm. This PRD is
the spec of record; the build follows it.

## 1. Problem statement

The stop-loss is not enforced anywhere (RISK-001). `stop_loss_threshold` exists only as a
sentence in the Claude prompt, evaluated once a day at 3:30 PM. Positions blow straight
through it: 13 closed round-trips realised **-10% to -24%** against a nominal 5% stop,
for an expectancy of roughly **-$58/trade** (15% win rate, average loser ~2× the average
winner). No factor tuning fixes a book with no working exits.

## 2. Strategic rationale

A disciplined trader defines risk *before* entry — the stop is what keeps you alive long
enough for any edge to matter. This project built sophisticated selection (screener,
sector rotation, Kelly sizing) on top of a non-existent exit. This PRD inverts the
priority: **Claude decides what to buy; the risk engine decides how much and when to get
out.**

## 3. User story

As the operator, I want every position to carry a broker-held stop sized to the stock's
own volatility, so that a loser is cut at a defined loss automatically — even at 11:42 AM
when nothing in the system is awake — rather than bleeding to -24% until the next daily
review.

## 4. Locked design decisions

From the 2026-07-22 brainstorm (do not re-litigate without new evidence):

1. **Model:** disciplined swing trader (keep the daily cadence; PDT rules make true
   intraday day-trading illegal under $25k anyway). [decided]
2. **Stop distance:** `2 × ATR(14)` below entry — volatility-adjusted, placed outside
   normal daily noise. ATR is already computed per ticker. [decided]
3. **Position size:** `risk_budget / stop_distance`, where `risk_budget = risk_pct ×
   equity` (default 1%). Volatile names get *smaller* positions automatically. [decided]
4. **Winner exits:** trailing stop, **no profit target**. Each cycle ratchets the stop up
   (never down); winners run until the trend breaks. [decided]
5. **Concentration:** portfolio heat cap (≤5% of equity at risk across open positions) +
   a per-sector cap (≤2 positions per industry). [decided]
6. **Scope:** risk engine + forex settings toggle only. Delete quarter-Kelly (superseded).
   Screener, sector rotation, earnings, decision modes, strategies, backtest, circuit
   breakers, compliance all untouched — so the next window measures exactly one change.
   [decided]
7. **Applies to a fresh Test 6**, not Test 5 in flight. Test 5 preserved like Test 4.
   [decided 2026-07-22]

## 5. Impact & KPIs

### (a) What the metric should be
Expectancy per trade turns positive (or at minimum beats the -$58/trade baseline) over
30+ executed trades, with the tail of large losses cut — no realised loss worse than
~1× the risk budget except on overnight gaps.

### (b) What we can measure today
`plan_snapshots` (now honest, post-2026-07-22 fix) gives weekly P&L for the Phase G gate.
Per-trade realised P&L is reconstructable from the `trades` ledger. Expectancy is not a
stored field — it is computed from the ledger. This is the EXP-002 experiment.

## 6. Technical approach

| Change | File | Notes |
|---|---|---|
| **New** `risk.py` — sizing, stop calc, heat, sector check | `app/risk.py` | App level (shared infra), not inside `plans/` — backtest may reuse it |
| Bracket order support (`stop_price`) | `brokers/base.py`, `brokers/alpaca.py` | `OrderClass.BRACKET` verified available; whole-share only; crypto = simple order |
| Wire sizing + caps + trailing ratchet into the cycle | `plans/executor.py` | Minimal touchpoints |
| `risk_pct`, `atr_multiple` on Portfolio; `stop_price` on Trade | `plans/models.py` | |
| **Delete** quarter-Kelly sizing | `position_sizing.py` | Superseded by risk-based sizing |
| Settings toggle hides forex nav group | `settings/page.tsx`, `TopNav.tsx` | localStorage pref, default off |
| Create Test 6 portfolio | one-off / seed | $10k, risk engine active |

### Failure modes (accepted / guarded)
- **No ATR → no trade.** Missing/zero ATR means no computable stop or size → skip + log.
  Same principle as the snapshot fix: missing data never becomes a number.
- **Whole-share flooring.** Bracket legs require whole shares; if size rounds to 0, no trade.
- **Gap-down through the stop.** A stop caps typical losses, not overnight gaps. This is
  the honest limit and the reason earnings-proximity sizing stays.
- **Crypto can't bracket.** Alpaca crypto is simple-order only → no broker stop; falls
  back to the daily check. Test 6 holds no crypto.

## 7. AI implementation notes
No change to the model call. Claude still decides buy/sell/hold; sizing and stops move
out of the prompt and into code. The prompt's stop-loss sentence becomes redundant and
should be removed to avoid implying the model controls exits.

## 8. Testing plan
TDD throughout. Unit: sizing math, stop calc, heat accumulation, sector counting,
ratchet-never-lowers, no-ATR-no-trade, whole-share flooring. Integration: bracket payload
reaches the broker; missing ATR blocks the trade. ~15-20 new tests on the 405 baseline.

## 9. Build phasing
Incremental, each phase shippable and tested:
- **Phase 1 (core):** `risk.py` sizing + ATR stop, bracket orders, model fields, executor
  entry wiring, Test 6. This is the load-bearing fix — stops become real.
- **Phase 2:** trailing ratchet on the daily cycle.
- **Phase 3:** heat cap + sector cap.
- **Phase 4:** delete quarter-Kelly, forex toggle, remove the prompt stop sentence.

## What we'd do differently (carried from PRD-001's lesson)
The exit engine should have existed before the selection engine. Building Kelly sizing and
a 650-name screener on top of an unenforced stop was effort spent on the wrong layer.
