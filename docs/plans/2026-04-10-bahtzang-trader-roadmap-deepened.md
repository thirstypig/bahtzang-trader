# bahtzang-trader — Deepened Roadmap & Architecture Plan

> **Deepened on:** 2026-04-10
> **Sections enhanced:** 6
> **Research agents used:** 8 (zero-commission APIs, admin/docs patterns, portfolio analytics, AI trading brain, risk management, skills/agents/learnings discovery)

## Enhancement Summary

### Key Improvements
1. **Multi-broker architecture** — Alpaca (stocks, ETFs, options, crypto — all $0) as primary, Schwab as safe harbor for treasuries/bonds
2. **Risk management is a full subsystem** — VaR, Kelly criterion position sizing, circuit breakers, PDT compliance, wash sale rules, disaster recovery
3. **Claude brain architecture refined** — two-tier screening (Python pre-filter → Claude synthesis), technical indicators computed in Python not by Claude, confidence calibration tracking
4. **12 pages total** — 3 main (dashboard, trades, settings) + 4 trading tools (analytics, paper trading, alerts, backtest) + 5 admin (roadmap, changelog, status, docs, about, audit log)
5. **Learnings from other projects applied** — CSP headers, Supabase auth gotchas, deployment patterns from fbst/fsvppro/bbq-judge

### New Considerations Discovered
- Supabase now uses ES256 JWT signing (not HS256) — already fixed in current codebase
- Pattern Day Trader (PDT) rule is a hard regulatory constraint for accounts under $25k
- Paper trading mode is essential before going live — minimum 30 trades or 2 weeks
- Claude has a conservative bias for trading decisions — prompt engineering needed to calibrate

---

## Phase 0: Stabilize Current Deployment (NOW)

**Status:** Backend live, frontend live, auth working, Schwab API not configured yet.

- [ ] Verify Schwab API credentials work (real or sandbox)
- [ ] Confirm trades table is created in Supabase
- [ ] Test full bot cycle manually via `POST /run`
- [ ] Remove `/debug` page after confirming auth works
- [ ] Set `CORS_ORIGINS` to `https://www.bahtzang.com` on backend

---

## Phase 1: Multi-Asset Trading Support

### Current State
Schwab-only, US equities, market orders.

### Target State
Multiple brokers, multiple asset classes, zero-commission where possible.

### Multi-Broker Architecture

**Strategy:** Each broker handles what it's best at. One unified `BrokerInterface` in our code.

| Broker | Role | Products | Commission | Why |
|--------|------|----------|------------|-----|
| **Alpaca** | Primary | Stocks, ETFs, Options, Crypto | $0 all | Best API + paper trading + zero fees |
| **Schwab** | Safe harbor | Treasuries, Bonds, CDs | $0 | Park idle cash in risk-free yield |

**Why NOT others:**
- **Coinbase**: Fees (0.1-0.6%), Alpaca already covers crypto
- **Robinhood**: No official API — not viable for bots
- **Interactive Brokers**: Fees ($1-4/trade), overkill for this scope
- **OANDA/Forex**: Forex adds complexity without clear AI edge

### Research Insights

**Best Practices:**
- Alpaca covers 90% of needs: stocks, ETFs, options, crypto — all $0, one API
- Use Alpaca's paper trading environment to validate Claude's decisions before going live
- Fractional shares enable precise portfolio rebalancing without needing large capital
- When Claude says "market is too risky, go to cash" → sweep to Schwab treasuries for yield
- Claude can trade across asset classes: "Sell AAPL stock, buy BTC" in a single cycle

**Implementation Plan:**
1. Create broker abstraction layer (`BrokerInterface` base class)
2. Implement `AlpacaBroker` (primary — stocks, ETFs, options, crypto)
3. Implement `SchwabBroker` (safe harbor — treasuries, bonds)
4. Route trades by asset class: equities/options/crypto → Alpaca, fixed-income → Schwab
5. Unified portfolio view aggregates positions across both brokers

**New Files:**
- `backend/app/brokers/__init__.py`
- `backend/app/brokers/base.py` — Abstract `BrokerInterface` with `get_positions()`, `place_order()`, `get_balance()`
- `backend/app/brokers/alpaca_client.py` — Primary broker (stocks, ETFs, options, crypto)
- `backend/app/brokers/schwab_client.py` — Move existing code here (treasuries, bonds)
- `backend/app/brokers/router.py` — Routes trades to correct broker by asset class

**New Env Vars:**
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_PAPER` (true/false — toggles paper trading mode)

**Edge Cases:**
- Alpaca crypto trades 24/7 but stocks are market hours only — scheduler needs asset-aware timing
- Fractional shares have different settlement rules (T+1 for crypto, T+2 for equities)
- Alpaca rate limits: 200 req/min paper, 300 live
- Cross-broker portfolio view must aggregate balances and positions from both APIs
- Claude's trade decision needs to specify asset class so the router picks the right broker

---

## Phase 2: Enhanced Claude Brain

### Current State
Single prompt to Claude Sonnet with current holdings + market data + news → one buy/sell/hold decision.

### Target State
Multi-tier screening pipeline, technical indicators, sector awareness, earnings integration, confidence calibration.

### Research Insights

**Architecture: Two-Tier Screening**
1. **Python pre-filter** (fast, no API cost): Compute RSI, MACD, Bollinger Bands, moving averages for universe of stocks. Filter to top 20-30 candidates by technical extremes.
2. **Claude synthesis** (slower, costs tokens): Analyze pre-filtered candidates with portfolio context, news, and earnings calendar. Rank opportunities, recommend top 3-5.

**Key Principle:** Python computes, Claude reasons. Don't waste tokens on math Claude can't do faster than numpy.

**Best Practices:**
- Feed Claude compact CSV data, not verbose JSON or prose
- Pre-compute indicators with `pandas-ta` (pure Python, no C dependencies like TA-Lib)
- Include only: ticker, price, RSI, MACD, SMA50/200, ATR, 1-week/1-month % change
- Force structured JSON output with explicit confidence scores (0-100)
- Track confidence calibration: "When Claude says 80% confidence, are 80% actually profitable?"

**Prompt Engineering for Trading:**
- Add chain-of-thought: "Show your reasoning before stating your action"
- Maintain 60/40 BUY bias when technicals align (counteract Claude's conservative nature)
- Separate conviction from position size: "HIGH conviction BUY with MEDIUM position size"
- Require risk/reward ratio for every recommendation (entry, stop, target)

**Technical Indicators to Feed Claude:**
| Indicator | Why | Compute With |
|-----------|-----|-------------|
| RSI (14) | Overbought/oversold extremes | `pandas-ta` |
| MACD (line + signal + histogram) | Trend direction + momentum shifts | `pandas-ta` |
| Bollinger Bands (20, 2) | Volatility context, mean reversion | `pandas-ta` |
| SMA 50 / SMA 200 | Trend regime (bull if above both) | `pandas-ta` |
| ATR (14) | Volatility for position sizing | `pandas-ta` |

**Indicators Claude Does NOT Need:** Ichimoku, Keltner channels, Stochastic, ADX — too specialized, Claude can infer from RSI/MACD.

**Earnings Calendar Integration:**
- Free API: Finnhub (`/calendar/earnings`) — 60 calls/min free tier
- Rule: Reduce position size 50% for holdings reporting this week
- Rule: Don't enter new positions in stocks reporting within 5 days
- Post-earnings: Analyze price reaction vs historical patterns before resuming

**Sector Rotation:**
- Track 10 sector ETFs (XLK, XLV, XLF, XLE, etc.) rolling 20/50/200-day performance
- Feed relative sector strength to Claude
- Claude identifies rotation patterns: "Money flowing from tech to healthcare"

**Multi-Model Consensus (Future):**
- Small account (<$25k): Single Claude Sonnet (cost-effective)
- Medium account ($25k-$100k): Sonnet primary + Opus for earnings/reversals
- Require 2/3 supermajority for action; disagreement = HOLD
- Estimated cost: ~$0.50-$2.00 per daily cycle with Sonnet

**New Files:**
- `backend/app/screener.py` — Universe screening with pandas-ta
- `backend/app/indicators.py` — Technical indicator computation
- `backend/app/earnings.py` — Earnings calendar from Finnhub
- `backend/app/sector_rotation.py` — Sector ETF tracking

**New Dependencies:** `pandas-ta`, `finnhub-python`

---

## Phase 3: Risk Management Subsystem

### Current State
Basic guardrails: max invested, max trade size, daily order limit, stop loss %, kill switch.

### Target State
Production-grade risk management: VaR, Kelly position sizing, circuit breakers, correlation monitoring, paper trading, regulatory compliance.

### Research Insights

**Position Sizing with Kelly Criterion:**
- Map Claude's confidence score directly to Kelly inputs
- Use **half-Kelly** for safety (full Kelly is mathematically optimal but volatile)
- For $50k portfolio with confidence=0.7: Kelly fraction ≈ 0.15 → half-Kelly = 0.075 → max position = $3,750
- Cap single position at 25% of portfolio regardless of Kelly output
- Calibrate over time: track actual win rate at each confidence level

**Value at Risk (VaR):**
- Start with **Historical VaR** (simplest, no distribution assumptions): sort 252 days of returns, find 5th percentile
- Target: 95% daily VaR < $2,500 (5% of $50k portfolio)
- Upgrade to Monte Carlo when portfolio exceeds 5+ assets (accounts for correlation)

**Circuit Breakers (staged, beyond kill switch):**

| Level | Trigger | Action |
|-------|---------|--------|
| 1 | Daily loss > 5% | HALT all trading for the day |
| 2 | Weekly loss > 10% | HALT for the week, require manual restart |
| 3 | 3+ consecutive losing trades | PAUSE, reassess Claude's prompt |
| 4 | VIX > 30 (market stress) | Reduce all position sizes by 50% |
| 5 | Kill switch (manual) | Halt everything immediately |

**Correlation Monitoring:**
- Calculate rolling 60-day correlation matrix between all held positions
- Alert when correlated group (r > 0.7) exceeds 50% of portfolio
- No single sector > 35% of portfolio
- Visualize as heatmap on the analytics dashboard

**Stop Loss Strategies for Daily Bot:**
1. **Schwab/Alpaca conditional orders (OCO)** — set at order entry, triggers automatically
2. **ATR-based stops** — wider stops for volatile stocks, tighter for stable
3. **Morning reconciliation** — at 9:35 AM, check if any overnight gaps hit stops

**Paper Trading Mode:**
- Toggle via `POST /paper-trading/start`
- Simulate slippage: 0.02% (small orders) to 0.20% (large)
- Simulate partial fills for illiquid stocks
- Track paper vs live performance separately
- Minimum 30 trades OR 2 weeks before graduating to live
- Target: Paper Sharpe ratio > 1.0

**Regulatory Compliance:**

| Rule | Constraint | Implementation |
|------|-----------|----------------|
| **PDT Rule** | Max 3 day trades in 5 business days (if equity < $25k) | Count day trades, block if approaching limit |
| **Wash Sale Rule** | Can't claim loss if repurchasing same security within 30 days | Check trade history before selling at a loss |
| **Best Execution** | Seek best available price | Use SMART routing (broker handles) |
| **Audit Trail** | Document all decision logic | Already logging to trades table |

**Disaster Recovery:**
- Idempotent order execution: generate `operation_id` before placing order, check for duplicates on restart
- Trade status field: `pending` → `executed` / `failed` / `rejected`
- Startup recovery: on app boot, reconcile pending trades with broker
- Fill reconciliation: check actual fills vs intended quantities

**New Files:**
- `backend/app/risk_management.py` — VaR, Kelly, correlation
- `backend/app/circuit_breaker.py` — Staged halt system
- `backend/app/compliance.py` — PDT, wash sale checks
- `backend/app/paper_trading.py` — Simulation with slippage
- `backend/app/disaster_recovery.py` — Idempotent execution, reconciliation

**Schema Changes:**
```sql
ALTER TABLE trades ADD COLUMN operation_id UUID;
ALTER TABLE trades ADD COLUMN status VARCHAR(20) DEFAULT 'executed';
ALTER TABLE trades ADD COLUMN paper_trading BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN slippage_pct FLOAT DEFAULT 0;
ALTER TABLE trades ADD COLUMN actual_quantity INTEGER;
ALTER TABLE trades ADD COLUMN schwab_order_id VARCHAR(100);

CREATE TABLE portfolio_snapshots (
  id SERIAL PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  total_value DECIMAL(15,2),
  cash_balance DECIMAL(15,2),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (snapshot_date)
);

CREATE TABLE daily_returns (
  id SERIAL PRIMARY KEY,
  date DATE NOT NULL,
  portfolio_return DECIMAL(10,6),
  benchmark_return DECIMAL(10,6),
  UNIQUE (date)
);
```

---

## Phase 4: Portfolio Analytics Dashboard

### Current State
Basic portfolio card (total value, cash, daily P&L), allocation pie chart, value-over-time line chart.

### Target State
Professional analytics: equity curve vs benchmark, drawdown chart, risk metrics, per-ticker P&L, return distribution.

### Research Insights

**Key Metrics to Display:**

| Metric | Formula | Target |
|--------|---------|--------|
| Sharpe Ratio | (Return - RiskFree) / StdDev × √252 | > 1.0 |
| Sortino Ratio | (Return - RiskFree) / DownsideDev × √252 | > 1.5 |
| Max Drawdown | (Peak - Trough) / Peak | < 15% |
| Win Rate | Winning Trades / Total Trades | > 55% |
| Profit Factor | Gross Profit / Gross Loss | > 1.5 |
| Calmar Ratio | Annual Return / Max Drawdown | > 0.5 |

**Best Practices:**
- Use **Time-Weighted Returns** for performance evaluation (eliminates deposit/withdrawal impact)
- Store daily portfolio snapshots for efficient analytics queries
- Pre-calculate metrics in materialized views or nightly batch jobs
- Compare against SPY (S&P 500 ETF) as benchmark

**Visualization (Recharts):**
- **Equity curve**: Line chart, portfolio vs SPY overlay
- **Drawdown (underwater plot)**: Area chart, negative fill (red)
- **Return distribution**: Histogram with normal distribution overlay
- **Monthly returns heatmap**: Custom grid component (Recharts can't do natively)
- **Correlation matrix**: Custom heatmap (or use `visx` for large matrices)

**Data Storage:**
- Daily `portfolio_snapshots` table for efficient analytics queries
- Consider TimescaleDB extension if storing millions of price quotes (not needed initially)
- FIFO cost basis tracking for per-ticker P&L and tax reporting

**Implementation:**
- Backend: New endpoints `GET /analytics/performance`, `GET /analytics/drawdown`, `GET /analytics/correlation`
- Compute Sharpe/Sortino/VaR with numpy in Python, return pre-calculated to frontend
- Frontend: New `/analytics` page with 4-6 chart components

---

## Phase 5: Admin & Documentation Pages

### Pages to Build

#### 1. `/roadmap` — Product Roadmap
- **Pattern:** Kanban board (Planned → In Progress → Done)
- **Data source:** JSON file initially, migrate to Supabase later
- **Components:** `RoadmapBoard`, `RoadmapCard` with priority badges and status colors
- **Columns:** 3-column grid layout matching dark theme

#### 2. `/changelog` — Release History
- **Pattern:** Reverse-chronological timeline with version badges
- **Data source:** JSON or auto-generated from conventional commits
- **Components:** `ChangelogEntry` with type badges (feat/fix/docs/perf)
- **Auto-generation:** Parse git history with `conventional-changelog`, or integrate with GitHub Releases API

#### 3. `/about` — How This Was Built
- **Content:** Architecture diagram (Mermaid.js), tech stack grid, design philosophy
- **Interactive:** Mermaid.js renders architecture diagrams in the browser
- **Package:** `npm install mermaid`
- **Layout:** Full-width hero, 2-column tech stack grid

#### 4. `/status` — Service Health
- **Services to monitor:** Backend API, Supabase, Schwab/Alpaca, Alpha Vantage, Finnhub
- **Pattern:** Green/yellow/red status badges with response times
- **Implementation:** Next.js API route (`/api/status`) pings each service, frontend polls every 5 minutes
- **Incident history:** Log outages to a `service_incidents` table

#### 5. `/docs` — Documentation Hub
- **Pattern:** Sidebar navigation + MDX content
- **Content:** Getting Started, API Reference, Trading Strategy, Configuration, Troubleshooting
- **Setup:** `@mdx-js/loader` + `@mdx-js/react` for markdown rendering
- **Layout:** Fixed sidebar (64px wide) + scrollable content area

#### 6. `/analytics` — Trading Performance (see Phase 4)

#### 7. `/paper-trading` — Paper vs Live Comparison
- **Pattern:** Split dashboard — paper portfolio on left, live on right
- **Metrics:** Side-by-side Sharpe ratio, win rate, P&L curves
- **Toggle:** Button to start/stop paper trading mode
- **Graduation criteria:** Display "Ready to go live" when paper Sharpe > 1.0 and 30+ trades

#### 8. `/alerts` — Notification Configuration
- **Alert types:** Price target hit, drawdown threshold, VIX spike, circuit breaker triggered, trade executed
- **Channels:** In-app toast, email (via Supabase), browser push notification
- **Pattern:** Table of alert rules with on/off toggles and threshold inputs

#### 9. `/backtest` — Strategy Backtesting Results
- **Pattern:** Date range selector + results dashboard
- **Charts:** Equity curve, drawdown, trade markers on price chart
- **Metrics:** Same as analytics but for historical simulation
- **Compare:** Multiple backtest runs side-by-side

#### 10. `/audit-log` — Full Activity Trail
- **Content:** Every bot action, config change, login, guardrail trigger, circuit breaker activation
- **Pattern:** Filterable log table with severity levels (info/warning/error)
- **Retention:** Keep 90 days, archive to cold storage
- **Regulatory:** Required for compliance documentation

### Navigation Update
```
Main:     Dashboard | Trades | Settings
Trading:  Analytics | Paper Trading | Alerts | Backtest
Admin:    Roadmap | Changelog | Status | Docs | About | Audit Log
```
12 pages total (plus /login). Group into a "More" dropdown or sidebar sections.

---

## Phase 6: Backtesting Framework (Future)

### Research Insights
- **Backtrader** (Python): Most flexible for LLM integration, can call Claude API per bar
- **Vectorbt**: NumPy-fast for pre-computed signal arrays, good for rapid iteration
- **Critical:** Prevent lookahead bias — use `i-1` data only (yesterday's close, not today's)
- **Metrics to track:** Win rate, profit factor, max drawdown, Sharpe, Claude's confidence calibration
- **Confidence calibration:** "When Claude says 80%, are 80% actually profitable?" — track this over time

---

## Applicable Learnings from Other Projects

### From FBST (Fantasy Baseball)
- **AI hallucination on null data** (`silent-null-causes-llm-hallucination.md`): When data is missing, Claude fills in plausible-sounding but wrong information. **Application:** If market data API returns null/empty, don't pass it to Claude — return a "data unavailable" error instead of letting Claude hallucinate prices.
- **Deployment checklist** (`DEPLOYMENT-CHECKLIST.md`): Production deployment gotchas with Railway, Cloudflare, CSP headers. **Application:** Follow the same deployment verification pattern.

### From FSVPPRO
- **CSP wildcard blocking** (`csp-wildcard-subdomain-matching.md`): Content Security Policy headers can silently block API calls. **Application:** If we add CSP headers, ensure Supabase and backend API domains are explicitly allowed.
- **Security hardening** (`comprehensive-codebase-review-security-hardening.md`): Auth bypass, privilege escalation, N+1 queries. **Application:** Run security review before going live with real money.

### From BBQ Judge
- **Supabase + Next.js 14 patterns**: Direct architectural match — same stack. **Application:** Reference their auth flow and data fetching patterns.

---

## Implementation Priority & Timeline

| Phase | What | Priority | Effort |
|-------|------|----------|--------|
| **Phase 0** | Stabilize deployment, verify end-to-end | **Critical** | 1-2 days |
| **Phase 1** | Multi-broker (Alpaca + Schwab) + paper trading | **High** | 1 week |
| **Phase 3** | Risk management (Kelly, circuit breakers, PDT) | **High** | 1-2 weeks |
| **Phase 2** | Enhanced Claude brain (screening, indicators) | **High** | 1-2 weeks |
| **Phase 5a** | Admin pages (roadmap, changelog, about, status, docs, audit log) | **Medium** | 1 week |
| **Phase 5b** | Trading tools (analytics, paper trading dashboard, alerts) | **Medium** | 1 week |
| **Phase 4** | Portfolio analytics (equity curve, drawdown, risk metrics) | **Medium** | 1 week |
| **Phase 6** | Backtesting framework + backtest page | **Low** | 2-3 weeks |

**Full page count:** 12 pages + login
- **3 existing:** Dashboard, Trades, Settings
- **4 trading tools:** Analytics, Paper Trading, Alerts, Backtest
- **6 admin:** Roadmap, Changelog, About, Status, Docs, Audit Log

**Note:** Phase 3 (risk management) is ordered before Phase 2 (enhanced brain) because you should never trade with real money without proper risk controls, even if the AI is good.

---

## Updated Environment Variables (All Phases)

### Backend (Railway)
| Variable | Phase | Source |
|----------|-------|--------|
| `ANTHROPIC_API_KEY` | 0 | Anthropic |
| `SCHWAB_CLIENT_ID` | 0 | Schwab |
| `SCHWAB_CLIENT_SECRET` | 0 | Schwab |
| `ALPHA_VANTAGE_KEY` | 0 | Alpha Vantage |
| `DATABASE_URL` | 0 | Supabase pooler |
| `SUPABASE_URL` | 0 | Supabase |
| `ALLOWED_EMAIL` | 0 | Your Gmail |
| `CORS_ORIGINS` | 0 | Your domain |
| `ALPACA_API_KEY` | 1 | Alpaca |
| `ALPACA_SECRET_KEY` | 1 | Alpaca |
| `ALPACA_PAPER` | 1 | `true` / `false` |
| `FINNHUB_API_KEY` | 2 | Finnhub |

### Frontend (Railway)
| Variable | Phase | Source |
|----------|-------|--------|
| `NEXT_PUBLIC_API_URL` | 0 | Backend Railway URL |
| `NEXT_PUBLIC_SUPABASE_URL` | 0 | Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | 0 | Supabase |
| `PORT` | 0 | `3060` |
| `HOSTNAME` | 0 | `0.0.0.0` |
