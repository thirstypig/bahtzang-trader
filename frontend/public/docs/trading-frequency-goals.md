# Trading Frequency & Goals — Deepened Plan

> **Created:** 2026-04-11
> **Deepened on:** 2026-04-11
> **Status:** Ready to implement
> **Context:** First trade (BUY VST) executed successfully. Bot runs 1x/day at 9:35 AM ET.
> **Research agents:** 4 (frequency best practices, goal strategies, portfolio analytics, technical indicators)

## Enhancement Summary

### Key Findings
1. **3x/day is the optimal frequency** — 9:35 AM, 1:00 PM, 3:45 PM ET captures open, midday, and close. Diminishing returns past 5x/day.
2. **6 trading goals** with specific tickers, Claude prompts, and expected returns for each
3. **pandas-ta** (pure Python, no C deps) for technical indicators — CSV format is most token-efficient for Claude
4. **Daily portfolio snapshots** at market close unlock all analytics (Sharpe, drawdown, equity curve)
5. **Alpha Vantage free tier limits 3x/day** — upgrade to Finnhub or Alpaca Data API for 5x+

---

## 1. Trading Frequency Control

### Optimal Schedule (Research-Backed)

| Preset | Times (ET) | Why |
|--------|-----------|-----|
| **1x/day** | 9:35 AM | Current default. Safe, minimal API usage |
| **3x/day** | 9:35 AM, 1:00 PM, 3:45 PM | **Recommended.** Captures open volatility, stable midday, closing momentum |
| **5x/day** | 9:35, 10:30, 12:00, 1:30, 3:00 | Aggressive. Requires Alpha Vantage premium or switch to Finnhub |

**Times to AVOID:** 11:30 AM - 1:30 PM (lunch lull — volume drops 30-50%, spreads widen)

### Strategy Mode by Time of Day
- **Morning (9:35 AM):** Breakout/momentum — gap fills, opening volatility
- **Midday (1:00 PM):** Mean reversion — support/resistance plays in stable conditions  
- **Close (3:45 PM):** Trend following — ride end-of-day institutional moves, tighter stops

### API Cost Impact

| Frequency | Alpha Vantage Calls/Day | Claude Calls/Day | Monthly Claude Cost |
|-----------|------------------------|-------------------|---------------------|
| 1x/day | 5-10 | 1 | ~$0.09 |
| 3x/day | 15-30 | 3 | ~$0.27 |
| 5x/day | 30-50 (needs premium) | 5 | ~$0.45 |

### Implementation

**Backend changes:**
- `guardrails.json`: Add `trading_frequency` field ("1x", "3x", "5x")
- `scheduler.py`: Dynamic job reconfiguration via `scheduler.remove_job()` + `scheduler.add_job()` with comma-separated CronTrigger hours
- Add 90-second timeout per cycle to prevent overlap
- `trade_executor.py`: Add `strategy_mode` parameter ("morning", "midday", "close") based on current time

**Frontend changes:**
- Settings page: Frequency selector (radio buttons) below risk profile
- Dashboard header: Show "Running 3x/day" badge

---

## 2. Trading Goals

### Goal Comparison Table

| Goal | Annual Return | Risk | Frequency | Hold Period | Min Confidence | Best For |
|------|--------------|------|-----------|-------------|----------------|----------|
| **Maximize Returns** | 15-30% | High | 3x/day | 5-30 days | 65% | Aggressive growth |
| **Steady Income** | 4-8% | Low | 1x/day | 30+ days | 70% | Dividends, retirees |
| **Capital Preservation** | 2-4% | Very Low | 1x/day | 30-90 days | 80% | Risk-averse |
| **Beat S&P 500** | 12-18% | Moderate | 2x/day | 10-45 days | 65% | Benchmark beaters |
| **Swing Trading** | 20-40% | High | 5x/day | 2-7 days | 60% | Active traders |
| **Passive Index** | 8-12% | Moderate | 1x/week | Indefinite | N/A | Buy-and-hold |

### Goal Details

#### Maximize Returns
- **Tickers:** AAPL, NVDA, MSFT, TSLA, GOOGL, AMZN, META, QQQ, XLK, BTC, ETH
- **Claude prompt:** "Seek highest risk-adjusted returns through momentum. 60% buy bias when technicals align. Hold cash 20% for dips."
- **Strategy:** RSI oversold bounces, MACD crossovers, sector momentum leaders

#### Steady Income
- **Tickers:** SCHD (3.2%), VYM (2.8%), JEPI (7.8%), O (3.6%), JNJ (2.5%), PG (2.3%)
- **Claude prompt:** "Generate 4-8% annual income through dividends. Only buy yield > 3.5% and payout ratio < 65%. HOLD 75% of the time."
- **Strategy:** Dividend aristocrats, covered calls on 100-share positions
- **Target:** $50k portfolio → ~$2,267/year income (4.5%)

#### Capital Preservation
- **Tickers:** SHV (5.1%), BIL (5.2%), XLU (2.8%), USMV (2.1%), PG, JNJ
- **Claude prompt:** "Preserve capital above all. 80% confidence minimum. If any position down > 8%, sell immediately. Cash reserve minimum 20%."
- **Circuit breakers:** VIX > 25 → reduce equities 50%. Daily loss > 5% → HALT 48 hours.

#### Beat S&P 500
- **Tickers:** 10 sector ETFs (XLK, XLV, XLF, XLE, XLI, XLY, XLP, XLB, XLRE, XLU)
- **Claude prompt:** "Outperform SPY by 2-8% through sector rotation. Overweight sectors beating SPY, underweight laggards."
- **Reality check:** Only 15-20% of active managers beat S&P 500 after fees. AI advantages: $0 fees, no emotion, rapid rotation.

#### Swing Trading
- **Tickers:** AAPL, MSFT, NVDA, TSLA, GOOGL, AMD, QQQ, BTC, ETH
- **Claude prompt:** "Capture 2-5% moves in 2-7 days. Take profits at 3-5%, cut losses at 5%. Max 5 simultaneous positions."
- **Setups:** RSI oversold bounce (50-60% win rate), MACD bullish crossover (55-65%), Bollinger breakout (50-55%)
- **PDT warning:** Requires $25k+ if day trading. Swing holds 2+ days avoid PDT rule.

#### Passive Index
- **Tickers:** VOO (65%), VTI (25%), VXUS (10%)
- **Claude prompt:** "Match S&P 500. HOLD 99% of the time. Only rebalance when drift > 5%. Never time the market."
- **Frequency:** 1x/week or 1x/month rebalancing check

### Implementation

**Backend changes:**
- `guardrails.json`: Add `trading_goal` field
- `claude_brain.py`: `GOAL_PROMPTS` dict with goal-specific Claude instructions (like we did for risk profiles)
- Goal affects: ticker universe, holding period, confidence threshold, position sizing
- Each goal auto-sets recommended frequency and risk profile

**Frontend changes:**
- Settings page: Goal selector (6 cards, similar to risk profile cards)
- Show goal description, expected returns, recommended frequency
- When goal changes, auto-suggest matching risk profile + frequency

---

## 3. Portfolio Analytics

### Data Architecture

**New tables:**
```sql
portfolio_snapshots: id, timestamp, total_equity, cash, invested, unrealized_pl
benchmark_prices: id, date, ticker (SPY), close_price
```

**Collection schedule:**
- Portfolio snapshot: Daily at 4:00 PM ET (market close) via APScheduler
- SPY benchmark: Daily at 4:30 PM ET via Alpaca Data API

### Analytics Endpoints

| Endpoint | Returns | Chart Type |
|----------|---------|-----------|
| `GET /analytics/equity-curve` | Portfolio value + SPY return % over time | ComposedChart (Area + Line overlay) |
| `GET /analytics/drawdown` | Peak-to-trough loss % series | AreaChart (red, negative fill) |
| `GET /analytics/sharpe` | Annualized Sharpe ratio + data points | KPI card |
| `GET /analytics/win-rate` | Wins/losses/avg P&L from closed trades | KPI cards |
| `GET /analytics/calibration` | Claude confidence vs actual accuracy | ScatterChart |
| `POST /snapshots/capture` | Manual snapshot trigger | Button |

### Statistical Notes
- Sharpe ratio needs 60+ daily snapshots for reliability (not meaningful yet with 1 trade)
- Win rate needs 20+ closed trades for significance
- Confidence calibration needs 50+ trades to detect patterns
- Show disclaimers in UI: "Insufficient data — need X more days"

### Implementation Priority
1. **Snapshot collection** (unlocks everything else)
2. **Equity curve vs SPY** (most visually impactful)
3. **Drawdown chart** (essential for risk monitoring)
4. **Win rate** (needs closed trades — will accumulate over time)
5. **Sharpe ratio** (needs 60+ days)
6. **Confidence calibration** (needs 50+ trades)

---

## 4. Enhanced Claude Brain — Technical Indicators

### Library: pandas-ta
- Pure Python, no C dependencies (unlike TA-Lib)
- 200+ indicators built-in
- New dependencies: `pandas==2.2.0`, `pandas-ta==0.3.14b0`

### Indicators to Compute

| Indicator | Bars Needed | What It Tells Claude |
|-----------|-------------|---------------------|
| RSI (14) | 14 | Oversold (<30) / Overbought (>70) |
| MACD (12,26,9) | 26 | Trend direction + momentum shifts |
| Bollinger Bands (20,2) | 20 | Volatility context, mean reversion zones |
| SMA 50 / SMA 200 | 200 | Trend regime (bull if price > both) |
| ATR (14) | 14 | Volatility for position sizing |

**Data requirement:** 250 days of daily OHLCV per ticker (covers SMA200 warmup)

### Token-Efficient Format for Claude

**Use CSV (most compact — 20 stocks in ~800 bytes):**
```
ticker,price,rsi,macd,bb_zone,sma_trend,atr
AAPL,150.25,28,−0.85,oversold,bullish,2.15
MSFT,380.10,55,0.45,neutral,bullish,3.20
```

### Sector Rotation
- Track 11 sector ETFs: XLK, XLV, XLF, XLE, XLI, XLY, XLP, XLB, XLRE, XLU, GLD
- Compute 20-day momentum for each
- Feed top 3 / bottom 3 to Claude: "Strongest: XLK +5.2%, Weakest: XLF −1.2%"

### Earnings Calendar
- Finnhub free API: 60 calls/min
- Filter out stocks reporting within 14 days (unless post-earnings play)
- New env var: `FINNHUB_API_KEY`

### New File: `backend/app/technical_analysis.py`
- `TechnicalAnalyzer` class with `analyze_stock()`, `analyze_many()`, `format_for_claude()`
- Integrates into `trade_executor.py` between data gathering and Claude call

---

## 5. Settings Page — Full Update

### New UI Sections (in order)

1. **Risk Profile** (existing) — Conservative / Moderate / Aggressive
2. **Trading Goal** (new) — 6 cards with icons, descriptions, expected returns
3. **Trading Frequency** (new) — 1x / 3x / 5x radio buttons with time display
4. **Fine-Tune Guardrails** (existing) — Individual overrides
5. **Emergency Controls** (existing) — Kill switch
6. **Manual Trigger** (existing) — Run Bot Now

### Goal + Frequency Auto-Linking
When a goal is selected, auto-suggest the matching frequency:
- Maximize Returns → 3x/day
- Steady Income → 1x/day
- Capital Preservation → 1x/day
- Beat S&P 500 → 2x/day
- Swing Trading → 5x/day
- Passive Index → 1x/week

User can override, but defaults are research-backed.

---

## Implementation Phases

| Phase | What | Effort | Dependencies |
|-------|------|--------|-------------|
| **A** | Trading goals (6 presets + Claude prompts) | 1-2 days | Risk profiles (done) |
| **B** | Trading frequency control (scheduler + UI) | 1-2 days | Goals (for auto-linking) |
| **C** | Portfolio snapshots + equity curve | 2-3 days | Alpaca connected (done) |
| **D** | Technical indicators (pandas-ta) | 2-3 days | Historical data source |
| **E** | Remaining analytics (drawdown, Sharpe, win rate) | 2-3 days | Snapshots (Phase C) |
| **F** | Sector rotation + earnings calendar | 1-2 days | Finnhub API key |

**Recommended order:** A → B → C → D → E → F
