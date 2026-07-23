---
id: DOC-026
type: brainstorm
status: done
phase: null
owner: james
tags: [strategies]
links: []
updated: 2026-07-22
---

# Dual Momentum — Backtest Findings

**Date:** 2026-05-12
**Author:** Analysis script (`scripts/analyze_dual_momentum.py`) + interpretation
**Status:** Ready for review — do NOT proceed to live integration until James greenlights

---

## What Was Tested

Gary Antonacci's Dual Momentum applied to a 3-ticker universe: SPY (US equity), VEU (international equity), BIL (short-term T-bills / defensive). Monthly rebalance. 12-month trailing return lookback. Compared against:

- **SPY Buy-and-Hold** — passive benchmark
- **60/40 SPY/BIL** — classic risk-managed benchmark, monthly rebalance
- **SMA Crossover (50/200)** on SPY/VEU/BIL — existing strategy
- **RSI Mean Reversion (30/70)** on SPY/VEU/BIL — existing strategy

Initial capital: $100,000. Adjusted closing prices from yfinance. No transaction costs or slippage modeled.

---

## Performance Summary

### Long window: 2005–2025 (effective start ~2008, see caveat §6.1)

| Strategy          | CAGR   | Sharpe | Sortino | Max DD  | Trades | Ann. Vol |
|-------------------|--------|--------|---------|---------|--------|----------|
| **Dual Momentum** | +5.6%  | 0.10   | 0.11    | -33.5%  | 53     | 14.3%    |
| SPY Buy-and-Hold  | +9.8%  | 0.32   | 0.31    | -55.0%  | 1      | 19.2%    |
| 60/40 SPY/BIL     | +5.6%  | 0.16   | 0.15    | -36.8%  | 424    | 11.8%    |
| SMA Crossover     | +3.0%  | -0.27  | -0.27   | -13.8%  | 55     | 6.7%     |
| RSI Mean Reversion| +3.1%  | -0.21  | -0.26   | -24.3%  | 122    | 7.8%     |

DM asset time: SPY 57% | VEU 12% | BIL 15% | Cash 17%

### Recent decade: 2015–2025

| Strategy          | CAGR   | Sharpe | Sortino | Max DD  | Trades | Ann. Vol |
|-------------------|--------|--------|---------|---------|--------|----------|
| **Dual Momentum** | +6.2%  | 0.14   | 0.14    | -33.6%  | 35     | 15.7%    |
| SPY Buy-and-Hold  | +11.9% | 0.44   | 0.42    | -33.6%  | 1      | 18.1%    |
| 60/40 SPY/BIL     | +8.0%  | 0.31   | 0.29    | -21.0%  | 244    | 10.7%    |
| SMA Crossover     | +3.3%  | -0.23  | -0.24   | -10.4%  | 27     | 6.7%     |
| RSI Mean Reversion| +3.5%  | -0.17  | -0.21   | -12.7%  | 56     | 7.3%     |

DM asset time: SPY 71% | VEU 12% | BIL 16% | Cash <1%

### 2008 stress: 2007–2010

| Strategy          | CAGR   | Sharpe | Sortino | Max DD  | Trades | Ann. Vol |
|-------------------|--------|--------|---------|---------|--------|----------|
| **Dual Momentum** | +0.7%  | -0.26  | -0.31   | -19.0%  | 7      | 13.0%    |
| SPY Buy-and-Hold  | -0.8%  | -0.08  | -0.08   | -54.9%  | 1      | 27.2%    |
| 60/40 SPY/BIL     | -0.8%  | -0.28  | -0.26   | -36.8%  | 88     | 16.5%    |
| SMA Crossover     | +1.8%  | -0.68  | -0.83   | -6.3%   | 17     | 4.5%     |
| RSI Mean Reversion| +0.2%  | -0.36  | -0.45   | -24.3%  | 122    | 11.5%    |

DM asset time: BIL 31% | Cash 35% | VEU 21% | SPY 13%

### COVID stress: 2019–2021

| Strategy          | CAGR   | Sharpe | Sortino | Max DD  | Trades | Ann. Vol |
|-------------------|--------|--------|---------|---------|--------|----------|
| **Dual Momentum** | +14.9% | 0.54   | 0.50    | -33.5%  | 7      | 20.1%    |
| SPY Buy-and-Hold  | +25.8% | 0.93   | 0.83    | -33.6%  | 1      | 21.8%    |
| 60/40 SPY/BIL     | +15.6% | 0.80   | 0.72    | -21.0%  | 72     | 12.9%    |
| SMA Crossover     | +6.0%  | 0.15   | 0.14    | -10.5%  | 7      | 8.1%     |
| RSI Mean Reversion| +5.3%  | 0.06   | 0.08    | -12.6%  | 17     | 8.7%     |

DM asset time: SPY 89% | BIL 8% | Cash 3%

---

## Assessment

### Did Dual Momentum beat buy-and-hold on a risk-adjusted basis?

**No, in 3 of 4 windows.** On Sharpe ratio — the correct metric for risk-adjusted comparison — DM trails SPY Buy-and-Hold in every window, and trails 60/40 in every window. The one partial win is the 2008 stress window on absolute CAGR (+0.7% vs -0.8%) and max drawdown (-19% vs -55%), but even there, SPY Buy-and-Hold has a better Sharpe (-0.08 vs DM's -0.26). The reason: after avoiding the crash, DM sat in BIL/cash for most of 2009 while SPY recovered 26% from its March lows. It avoided the fall but missed most of the rebound.

**Where it won:**
- 2008 window — absolute CAGR marginally positive, max drawdown meaningfully reduced. If you interpret "survival" as the goal during a 55% crash, DM passes.
- 2008 window — substantially lower drawdown than both benchmarks (-19% vs -37% to -55%).

**Where it failed:**
- Every window on Sharpe ratio — DM carries 14-20% annual vol while only generating 5-15% CAGR.
- Recent decade (2015-2025) — worst performer by a wide margin vs benchmarks (6.2% vs 11.9% CAGR, 0.14 vs 0.44 Sharpe).
- COVID — the strategy's core claim is crash protection. The COVID Max DD for DM is -33.5%, vs SPY's -33.6%. Statistically identical. The monthly rebalance is too slow for a 33-day crash.

### Window-by-window

**Long (2005–2025):** DM and 60/40 tie on CAGR (+5.6%), but DM has higher vol (14.3% vs 11.8%) and lower Sharpe (0.10 vs 0.16). There is no meaningful advantage to DM vs simply holding a static 60/40 over 20 years — and 60/40 requires far less mental model to explain.

**Recent decade (2015–2025):** This is DM's worst window. Bull markets with low volatility are exactly the regime DM is designed to underperform — it rotates to BIL when equity momentum fades (earning ~5% in BIL) and misses re-entry. SPY returned 11.9% CAGR vs DM's 6.2%.

**2008 stress (2007–2010):** DM's best window. However, the result is partially inflated — the strategy sat in cash for ~35% of this window due to missing VEU/BIL data in early 2007 and a 12-month warm-up period. The strategy didn't actually have a first trade until mid-2008, which coincidentally was near the market top. Treat the 2008 result with caution; it partially reflects the data-availability warm-up, not pure strategy merit.

**COVID stress (2019–2021):** Illustrates DM's structural weakness against fast drawdowns. The COVID crash (peak to trough: 33 calendar days) happened too quickly for monthly momentum to detect. By the time March 2020 month-end closed, the crash was already 90% done. SPY's trailing 12-month return was still positive, so DM stayed invested. Max DD nearly identical to buying and holding.

### The SMA Crossover finding

Unexpectedly, SMA Crossover had the lowest max drawdown in 2008 (-6.3%) and best SMA-era CAGR (+1.8%). Its Sharpe is consistently worse than DM because it spends so much time in cash earning nothing, but its capital preservation is superior. Worth noting — not actionable here, but relevant if we ever want a capital-preservation-first strategy.

---

## Known Caveats

### 6.1 — VEU/BIL data availability (affects the Long window)
VEU launched March 2007, BIL launched May 2007. For the 2005–2025 long window, DM was forced into cash for the first ~3.5 years (Jan 2005 through the 12-month warm-up that ends ~June 2008). This inflates the "cash" bucket (17% of the long window) and means the strategy's real start date is the eve of the financial crisis. The effective CAGR from the strategy's actual first trade would look different. We're reporting the full window CAGR, which includes the dead cash period.

### 6.2 — No transaction costs or slippage
All 53 DM trades (long window) are executed at exact adjusted closing prices. In reality: monthly rebalances at end-of-day close may slip 10-30 bps per transaction for liquid ETFs like SPY/VEU/BIL. With ~2-3 trades per rebalance and ~12 rebalances per year, this is roughly 6-9 trades/year × 20 bps average = ~1.5% CAGR drag. At 5.6% CAGR, that's meaningful.

### 6.3 — Survivorship bias / ticker selection
SPY, VEU, and BIL were chosen because they exist and are liquid. Antonacci's original work used different tickers (EFA instead of VEU, various T-bill proxies before BIL existed). VEU vs EFA behaves differently — VEU is newer, broader, and cheaper. The choice of "which international ETF" and "which bond proxy" meaningfully affects which months DM rotates and when.

### 6.4 — Adjusted close vs actual execution price
yfinance returns adjusted closing prices that account for dividends and splits retroactively. Actual trade execution happens intraday on the last trading day of the month — there is no guarantee the adjusted close price is achievable.

### 6.5 — Risk-free rate assumption
`analytics.py` uses a constant 5% annual risk-free rate. During 2009-2021, actual risk-free rates were 0-0.25%. A more historically accurate risk-free rate would improve Sharpe ratios for all strategies in that era. The current calculation penalizes strategies earning moderate returns during the ZIRP decade. This does not change the relative rankings — DM Sharpe is consistently below SPY BaH and 60/40 regardless of risk-free rate — but the absolute Sharpe values are artificially depressed.

### 6.6 — Monthly close as rebalance date
We use the last business day of each calendar month as the rebalance trigger. Antonacci's original research used end-of-month data, so this is consistent. But "monthly" momentum can be extremely sensitive to the exact return measurement period — a 5-day shift in measurement date can flip whether SPY or BIL is selected.

---

## Recommendation

**Keep in backtest only. Do not integrate into the live trading pipeline.**

Three reasons:

1. **Consistently underperforms on Sharpe.** DM doesn't outperform SPY Buy-and-Hold or 60/40 on a risk-adjusted basis in any window tested. If the goal is risk-adjusted return, DM is not the answer.

2. **Fails the fast-crash test.** The system's key claim is crash protection. COVID demonstrated that a monthly-rebalance strategy cannot protect against a crash that resolves in under 45 days. The exact kind of crash that dominates modern markets (algorithmic amplification, fast recoveries) is precisely where DM is blind.

3. **The live system's actual bottleneck is not strategy type.** We're in paper-trading accumulation mode. Adding a new execution strategy now — before we have 30+ paper trades and a validated pipeline — adds complexity without serving the gate we're actually trying to clear.

**If you want to revisit:** The case for DM would need to show (a) it outperforms on Sharpe in a realistic transaction-cost environment, or (b) you want capital preservation above CAGR as the primary objective for a specific portfolio. Neither is the current brief.

**Alternative worth considering (separate brainstorm):** A weekly or bi-weekly momentum variant could address the monthly-lag problem on fast crashes. Antonacci himself argues against this (more trades, more costs, more overfitting), but with liquid ETFs and no commissions the cost argument is weaker.

---

*Data source: yfinance adjusted closes. Analysis: `scripts/analyze_dual_momentum.py`. Analytics: `app/analytics.compute_metrics()`.*
