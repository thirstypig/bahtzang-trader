# bahtzang-trader — Deepened Roadmap & Architecture Plan

> **Created:** 2026-04-10
> **Deepened on:** 2026-04-12 (second pass)
> **Sections enhanced:** 8
> **Research agents used:** 13 (portfolio analytics, technical indicators, risk management, trade notifications, Alpaca Data API, code review agents from 2026-04-12)

## Enhancement Summary

### Key Improvements (2026-04-12 Deepening)
1. **Portfolio snapshots architecture** — APScheduler job at 4:05 PM ET, store SPY close alongside equity, numpy-based metrics engine, Sharpe confidence indicator
2. **Data pipeline overhaul** — Alpaca Data API replaces Alpha Vantage for OHLCV (200 req/min vs 25/day), Alpha Vantage kept only for news sentiment
3. **CSV prompt format** — 56% fewer tokens than JSON for Claude's technical analysis input, ~$0.01/day at 3 cycles
4. **Risk management refined** — Quarter-Kelly (not half), circuit breakers on portfolio P&L (not market VIX), Alpaca has built-in PDT protection
5. **Trade notifications** — Slack webhook via existing httpx, zero new dependencies, fire-and-forget pattern
6. **Guardrails migrated to PostgreSQL** — Completed 2026-04-12, fixes ephemeral filesystem, enables audit trail
7. **24 code review findings resolved** — All P1/P2/P3 items from 8-agent review fixed and merged

### Completed Since Last Deepening
- Phase 0: Fully stabilized
- Phase 1: Multi-broker with Alpaca primary, broker abstraction done
- Phase 5a: All 12 admin pages built
- Trading goals (6 presets) + frequency control (1x/3x/5x) wired to APScheduler
- Guardrails migrated from JSON file to PostgreSQL
- Kill switch activate + deactivate endpoints with audit trail
- Rate limiting (slowapi), security headers, async Alpaca SDK, Claude 30s timeout
- 44/44 code review todos resolved

---

## Remaining Phases (Updated Priority Order)

| Phase | What | Priority | Effort | Dependencies |
|-------|------|----------|--------|-------------|
| **A** | Trade Notifications (Slack) | **High** | 1-2 hours | None |
| **B** | Portfolio Snapshots + Equity Curve | **High** | 2-3 days | None |
| **C** | Technical Indicators (pandas-ta) | **High** | 2-3 days | Alpaca Data API |
| **D** | Risk Management (Kelly, circuit breakers) | **High** | 1-2 weeks | 30+ trades for Kelly calibration |
| **E** | Analytics (Sharpe, drawdown, win rate) | **Medium** | 2-3 days | Phase B snapshots |
| **F** | Backtesting Framework | **Low** | 2-3 weeks | Phases C + D |

**Recommended order:** A → B → C → E → D → F

Rationale: Notifications (A) is a 1-hour quick win. Snapshots (B) must come before analytics (E). Technical indicators (C) are independent. Risk management (D) needs trade history for Kelly calibration — start collecting data now, deploy Kelly after 30+ trades. Backtesting (F) requires indicators + risk management.

---

## Phase A: Trade Notifications (NEW)

### Overview
Add Slack webhook notifications so you don't have to visit bahtzang.com to know when trades execute.

### Research Insights

**Why Slack wins over alternatives:**

| Channel | Setup | New Deps | Cost | Best For |
|---------|-------|----------|------|----------|
| **Slack webhook** | 5 min | None (httpx) | Free | Everything |
| Discord webhook | 5 min | None (httpx) | Free | If you prefer Discord |
| Telegram bot | 15 min | None (httpx) | Free | Mobile-first |
| Email (Resend) | 20 min | resend SDK | Free tier | Formal alerts |
| SMS (Twilio) | 20 min | twilio SDK | ~$1.15/mo | Kill switch only |

**Architecture: Fire-and-forget with logging on failure.** A failed notification should never block or delay trade execution.

### Implementation

**New file: `backend/app/notifier.py`**
- `notify(message, level)` — async POST to Slack webhook
- `format_trade_executed(result)` — "BUY 10 AAPL at $180.50 — confidence 72%"
- `format_trade_blocked(result)` — "BLOCKED: Daily order limit reached"
- `format_kill_switch(activated)` — "KILL SWITCH ACTIVATED/DEACTIVATED"
- `send_daily_summary(stats)` — "Today: 2 trades, portfolio +1.2%"
- Silent no-op if `SLACK_WEBHOOK_URL` is empty

**Integration points:**
- `trade_executor.py:118` — after `log_trade()`, call `notifier.send_trade_notification(result)`
- `routes/guardrails.py:88,102` — kill switch activate/deactivate
- `scheduler.py` — add 4:05 PM ET daily summary job

**Config:** Add `SLACK_WEBHOOK_URL: str = ""` to `config.py`

**Message formatting (Slack mrkdwn):**
```
:white_check_mark: *BUY 10 shares AAPL* at $180.50
Confidence: 72% | Reasoning: Strong earnings beat...

:no_entry: *BLOCKED:* Daily order limit reached (5/5)

:rotating_light: *KILL SWITCH ACTIVATED* — all trading halted

:chart_with_upwards_trend: *Daily Summary — Apr 12, 2026*
Trades: 2 executed, 1 blocked | Portfolio: $52,340 (+1.2%)
```

**Avoiding notification fatigue:**
- Do NOT notify on "hold" decisions (most common outcome)
- One daily summary at market close, not per-cycle summaries
- Kill switch alerts are un-silenceable

### Acceptance Criteria
- [ ] Trade execution triggers Slack notification with ticker, quantity, price, confidence
- [ ] Guardrail blocks trigger notification with reason
- [ ] Kill switch activate/deactivate triggers notification
- [ ] Daily summary at 4:05 PM ET
- [ ] No notification on hold decisions
- [ ] Bot works normally if SLACK_WEBHOOK_URL is empty

---

## Phase B: Portfolio Snapshots + Equity Curve

### Overview
Store daily portfolio state at market close, track performance vs SPY benchmark, display equity curve chart.

### Research Insights

**Snapshot timing:** 4:05 PM ET (not 4:00 sharp) — Alpaca needs a few minutes to settle final mark-to-market values.

**SPY benchmark data:** Use Alpaca Data API (`StockHistoricalDataClient`), NOT Alpha Vantage. Store SPY close in the snapshot row so you never need to re-fetch.

**Use `db.merge()` for upsert:** If the job fires twice (Railway restart), merge handles the unique date constraint gracefully.

**Sharpe ratio needs ~60 trading days** for statistical significance at 95% confidence. Show the metric early but with a confidence indicator: "Sharpe: 1.24 (low confidence — 22/60 days)".

### New Model

```python
class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    invested: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    spy_close: Mapped[float] = mapped_column(Float, nullable=True)
    deposit_withdrawal: Mapped[float] = mapped_column(Float, default=0.0)
```

### New Files
- `backend/app/analytics.py` — numpy-based metrics: Sharpe, Sortino, max drawdown, win rate, profit factor, TWR
- `frontend/src/components/EquityCurveChart.tsx` — LineChart: portfolio (emerald) vs SPY (zinc-400, dashed)
- `frontend/src/components/DrawdownChart.tsx` — AreaChart with red gradient fill

### API Endpoints
- `GET /portfolio/snapshots?days=90` — daily snapshots for charting
- `GET /portfolio/metrics` — computed Sharpe, Sortino, drawdown, win rate, profit factor
- `POST /portfolio/snapshot` — manual snapshot trigger

### Scheduler
- Add 4:05 PM ET Mon-Fri job: fetch equity from Alpaca, SPY close from Alpaca Data API, save to DB

### Recharts Chart Types
| Chart | Component | Recharts Type |
|-------|-----------|---------------|
| Equity curve vs SPY | `LineChart` with 2 `Line` | Normalized % return from day 1 |
| Drawdown | `AreaChart` with red `linearGradient` | Always zero or negative |
| Return distribution | `BarChart` histogram | Pre-bucketed daily returns |
| Key metrics | Stat cards (existing pattern) | Color-coded: green/amber/red |

### Critical Pitfalls
1. Compute returns from total equity snapshots, NOT trade P&L (misses dividends, cash drag)
2. Don't annualize Sharpe with fewer than 20 data points
3. Always normalize to % return when comparing portfolio to SPY
4. Handle missed snapshot days gracefully (leave gap, don't interpolate)

### Acceptance Criteria
- [x] Daily snapshot captured at 4:05 PM ET with equity, cash, invested, SPY close
- [x] Equity curve chart shows portfolio vs SPY normalized returns
- [x] Drawdown chart shows peak-to-trough losses
- [x] Sharpe/Sortino/drawdown/win rate displayed with confidence indicators
- [x] Duplicate snapshots handled via upsert

---

## Phase C: Technical Indicators (pandas-ta)

### Overview
Compute RSI, MACD, Bollinger Bands, SMA, ATR from historical OHLCV data and feed them to Claude in token-efficient CSV format.

### Research Insights

**Data source overhaul:** Replace Alpha Vantage for OHLCV with Alpaca Data API.

| Feature | Alpaca (Free) | Alpha Vantage (Free) |
|---------|--------------|---------------------|
| Rate limit | **200 req/min** | 25 req/day |
| Historical OHLCV | 5+ years | 20+ years |
| Multi-symbol fetch | **Yes (1 API call)** | No (1 call per ticker) |
| Already integrated | **Yes (alpaca-py)** | Yes (httpx) |

**Keep Alpha Vantage for news sentiment only** — Alpaca doesn't offer news.

**Token efficiency:** CSV format uses **56% fewer tokens** than JSON with no accuracy loss.

**Cache strategy:** Compute indicators once daily at pre-market (9:00 AM ET), cache in memory. Daily indicators cannot change intraday.

### Implementation

**Pipeline architecture:**
```
[9:00 AM ET - Pre-market]
  → Alpaca StockHistoricalDataClient.get_stock_bars()
    - 20 portfolio tickers + 11 sector ETFs = 31 symbols
    - 1 API call, TimeFrame.Day, start=365d ago
  → validate_ohlcv() per ticker
  → pandas-ta Strategy (RSI, MACD, BBands, SMA50, SMA200, ATR)
  → Extract latest row → indicator_cache dict

[9:35 AM ET - Trading cycle]
  → Read cached indicators + fresh live quote
  → Format as CSV → append to Claude prompt
```

**Indicators to compute:**

| Indicator | Bars Needed | What It Tells Claude |
|-----------|-------------|---------------------|
| RSI (14) | 14 | Oversold (<30) / Overbought (>70) |
| MACD (12,26,9) | 26 | Trend direction + momentum shifts |
| Bollinger Bands (20,2) | 20 | Volatility context, mean reversion |
| SMA 50 / SMA 200 | 200 | Trend regime (bull if price > both) |
| ATR (14) | 14 | Volatility for position sizing |

**CSV format for Claude (~400 tokens for 20 stocks):**
```
TECHNICALS (daily):
ticker,price,rsi14,macd,macd_sig,bb_upper,bb_lower,sma50,sma200,atr14
AAPL,213.45,58.3,1.24,0.87,218.90,207.10,210.50,195.20,4.12
NVDA,134.20,62.1,2.15,1.90,140.50,128.30,131.40,118.60,5.85
```

**Sector rotation (CSV, ~150 tokens for 11 sectors):**
```
SECTOR ROTATION (vs SPY):
etf,rs_trend,perf_1m%,perf_3m%,rsi14
XLK,LEADING,+4.2,+12.1,61.3
XLF,LEADING,+2.8,+8.5,55.7
XLE,LAGGING,-1.2,+3.1,42.8
```

Relative strength = sector ETF price / SPY price. LEADING = ratio above 50-day SMA.

### New Files
- `backend/app/technical_analysis.py` — `TechnicalAnalyzer` class with indicator computation, caching, CSV formatting
- `backend/app/sector_rotation.py` — Sector ETF relative strength vs SPY

### New Dependencies
- `pandas-ta` (or `pandas-ta-classic`, the maintained fork)
- `pandas` (likely already a transitive dep of alpaca-py)

### Acceptance Criteria
- [x] Historical OHLCV fetched from Alpaca Data API (not Alpha Vantage)
- [x] All 5 indicator groups computed via pandas-ta
- [x] Indicators cached daily, recomputed only on first cycle of each day
- [x] Claude receives CSV-formatted technical data (~400 tokens for 20 stocks)
- [x] Sector rotation signals computed for 11 ETFs with LEADING/LAGGING labels
- [x] Missing data handled: forward-fill up to 5 days, NaN for insufficient history

---

## Phase D: Risk Management Subsystem

### Overview
Production-grade risk controls: Kelly position sizing, circuit breakers, PDT compliance, wash sale detection, VaR calculation.

### Research Insights

**Quarter-Kelly, not half-Kelly.** Professional quant funds use 10-25% of full Kelly. Half-Kelly is textbook but over-aggressive when your edge estimate (Claude's confidence) isn't calibrated. Use `confidence ** 2` as modifier to heavily penalize low-confidence trades.

**Circuit breakers: trigger on YOUR P&L, not VIX.** If the market drops 3% but your portfolio only drops 1%, that's not a circuit breaker event — the bot might want to buy the dip.

**Alpaca has built-in PDT protection** — rejects orders that would trigger PDT for accounts <$25k. But track yourself for UI visibility and to avoid surprise rejections.

### Circuit Breaker Tiers

| Level | Trigger | Action | Auto-Reset? |
|-------|---------|--------|-------------|
| YELLOW | Daily loss > 3% | Halve Kelly fraction | Next trading day |
| ORANGE | Weekly loss > 7% or 3+ consecutive losses | Halt new buys, allow sells | Next trading day |
| RED | Daily loss > 5% or weekly > 10% or 5+ consecutive losses | Full halt (flip kill switch) | Manual only |

### Implementation Order (within this phase)
1. **PDT compliance** — add to `check_guardrails()`, quick win
2. **Circuit breakers** — new `circuit_breaker.py`, called before Claude
3. **Wash sale detection** — new `wash_sale.py`, flag but don't block by default
4. **Kelly position sizing** — new `position_sizing.py`, needs 30+ trades for calibration
5. **VaR calculation** — new `var_calculator.py`, informational first, then connect to circuit breakers

### New Model Fields (GuardrailsConfig)
- `kelly_fraction: float = 0.25`
- `circuit_breaker_daily_pct: float = 0.05`
- `circuit_breaker_weekly_pct: float = 0.10`
- `respect_wash_sale: bool = True`
- `pdt_protection: bool = True`

### New Files
- `backend/app/position_sizing.py` — Kelly criterion with quarter-Kelly default
- `backend/app/circuit_breaker.py` — Three-tier staged halt system
- `backend/app/wash_sale.py` — 30-day cooling period tracking
- `backend/app/compliance.py` — PDT day trade counting
- `backend/app/var_calculator.py` — Historical simulation VaR (non-parametric)

### Acceptance Criteria
- [ ] Kelly sizes positions based on historical win rate + Claude confidence
- [ ] Circuit breakers trigger on portfolio drawdown, not market volatility
- [ ] PDT day trades counted and displayed in UI
- [ ] Wash sale cooling periods tracked (30-day rebuy restriction after loss sale)
- [ ] VaR calculated daily and displayed on analytics dashboard

---

## Phase E: Analytics Dashboard (Enhanced)

### Overview
Extend the existing `/analytics` page with the metrics computed from Phase B snapshots.

### Key Metrics Display

| Metric | Formula | Target | Confidence Threshold |
|--------|---------|--------|---------------------|
| Sharpe Ratio | (Return - RiskFree) / StdDev x sqrt(252) | > 1.0 | 60 days |
| Sortino Ratio | (Return - RiskFree) / DownsideDev x sqrt(252) | > 1.5 | 60 days |
| Max Drawdown | (Peak - Trough) / Peak | < 15% | 20 days |
| Win Rate | Winning Days / Total Days | > 55% | 20 days |
| Profit Factor | Gross Profit / Gross Loss | > 1.5 | 20 days |
| Calmar Ratio | Annual Return / Max Drawdown | > 0.5 | 90 days |

Show confidence indicators: "Sharpe: 1.24 (low confidence — 22/60 days)" with progress bar.

### New Chart Components
- `EquityCurveChart.tsx` — Portfolio vs SPY (from Phase B)
- `DrawdownChart.tsx` — Peak-to-trough visualization (from Phase B)
- `ReturnDistributionChart.tsx` — Histogram of daily returns
- `CalibrationChart.tsx` — Claude confidence vs actual accuracy (scatter plot, needs 50+ trades)

### Acceptance Criteria
- [ ] All metrics computed server-side via numpy, returned as JSON
- [ ] Metrics show confidence level based on data quantity
- [ ] Charts render with proper dark theme styling
- [ ] "Insufficient data" disclaimers shown when appropriate

---

## Phase F: Backtesting Framework (Future)

### Overview
Replay historical data through Claude to evaluate strategies before going live.

### Research Insights
- **Backtrader** (Python) — most flexible for LLM integration, can call Claude per bar
- **Vectorbt** — numpy-fast for pre-computed signal arrays, good for rapid iteration
- **Critical:** Prevent lookahead bias — use `i-1` data only (yesterday's close, not today's)

### Acceptance Criteria
- [ ] Date range selector for backtest period
- [ ] Equity curve + drawdown + trade markers on results page
- [ ] Same metrics as live analytics (Sharpe, win rate, etc.)
- [ ] Compare multiple backtest runs side-by-side
- [ ] Lookahead bias prevention verified

---

## Paper-to-Live Transition Plan

### Graduated Scale-Up
1. **Paper phase (current):** Run for 60+ days with full risk stack active. Track all metrics.
2. **Shadow mode (2-4 weeks):** Run live + paper simultaneously. Start with 10% of capital.
3. **Scale-up:** 10% → 25% (week 3-4) → 50% (month 2) → 100% (month 3+, if metrics hold)

### Safety Measures for Going Live
- Auto-apply "conservative" preset as floor when switching to live
- Add `max_live_loss_per_day: float` hard dollar cap (separate from % circuit breaker)
- Notification on every live trade (Phase A)
- Weekly review ritual: check VaR accuracy, recalibrate Kelly from updated win rates

### Config
- `ALPACA_PAPER: bool` already exists in `config.py`
- Add `LIVE_TRADING_MAX_CAPITAL_PCT: float = 0.10` for gradual scale-up
- Add capital throttle in `trade_executor.py`

---

## Updated Environment Variables

### Backend (Railway)
| Variable | Status | Source |
|----------|--------|--------|
| `ANTHROPIC_API_KEY` | Active | Anthropic |
| `SCHWAB_CLIENT_ID` | Optional (default "") | Schwab |
| `SCHWAB_CLIENT_SECRET` | Optional (default "") | Schwab |
| `ALPHA_VANTAGE_KEY` | Active (news only) | Alpha Vantage |
| `DATABASE_URL` | Active | Supabase pooler |
| `SUPABASE_URL` | Active | Supabase |
| `ALLOWED_EMAIL` | Active | Your Gmail |
| `CORS_ORIGINS` | Active | Your domain |
| `ALPACA_API_KEY` | Active | Alpaca |
| `ALPACA_SECRET_KEY` | Active | Alpaca |
| `ALPACA_PAPER` | Active (true) | true/false |
| `SLACK_WEBHOOK_URL` | **New (Phase A)** | Slack app |
| `FINNHUB_API_KEY` | Future (Phase C) | Finnhub |

---

## Sources & References

### Portfolio Analytics
- [Sharpe Ratio for Algorithmic Trading — QuantStart](https://www.quantstart.com/articles/Sharpe-Ratio-for-Algorithmic-Trading-Performance-Measurement/)
- [Probabilistic Sharpe Ratio: Minimum Track Record Length](https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-bias-adjustment-confidence-intervals-hypothesis-testing-and-minimum-track-record-length/)
- [Time-Weighted Return — Wikipedia](https://en.wikipedia.org/wiki/Time-weighted_return)
- [Recharts Examples](https://recharts.github.io/en-US/examples/)

### Technical Indicators
- [GetCrux: CSV vs JSON format for LLMs (56% token savings)](https://www.getcrux.ai/blog/experiment-data-formats---json-vs-csv)
- [Alpaca Historical Bars API](https://docs.alpaca.markets/reference/stockbars)
- [pandas-ta on PyPI](https://pypi.org/project/pandas-ta/)
- [Sector Rotation — Relative Strength Analysis](https://trendspider.com/blog/sector-rotation-how-to-track-where-the-money-is-moving/)

### Risk Management
- [Kelly Criterion for Algo Trading — QuantConnect](https://www.quantconnect.com/research/18312/kelly-criterion-applications-in-trading-systems/)
- [Why Fractional Kelly: Simulations with Uncertainty](https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html)
- [Alpaca PDT Protection](https://docs.alpaca.markets/docs/user-protection)
- [Schwab: Primer on Wash Sales](https://www.schwab.com/learn/story/primer-on-wash-sales)
- [Historical Simulation VaR with Python](https://medium.com/@matt_84072/historical-simulation-value-at-risk-explained-with-python-code-a904d848d146)

### Notifications
- [Slack Incoming Webhooks](https://api.slack.com/incoming-webhooks)
- [Slack Rate Limits](https://docs.slack.dev/apis/rate-limits/)

### Paper-to-Live
- [Alpaca: Paper Trading vs Live Trading Guide](https://alpaca.markets/learn/paper-trading-vs-live-trading-a-data-backed-guide-on-when-to-start-trading-real-money)
