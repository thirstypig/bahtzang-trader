# CLAUDE.md — bahtzang-trader

## Current status

<!-- now-tldr -->
An AI trading experiment — Claude makes the buy / sell / hold calls, a small web app handles the data and execution, and a paper-trading account at Alpaca is the live target (no real money yet). 24/30 paper trades executed (as of 2026-05-14); 6 more needed to gate the Phase G live switch. Only Test 4 ($10k portfolio) is active; three $100 test portfolios deactivated (spent). Fixed: BTC/ETH removed from Claude prompts (StockHistoricalDataClient returned wrong $35 price for crypto tickers). Decision modes, oversight activity, pause/resume UI, sign-out all shipped.
<!-- /now-tldr -->

## Project Overview
AI-powered trading bot with a Next.js dashboard and FastAPI backend. Claude Sonnet analyzes portfolio, market data, and news to make buy/sell/hold decisions. Guardrails enforce risk limits before execution.

## Architecture
```
Monorepo: /frontend (Next.js 14) + /backend (Python FastAPI)
Auth:     Supabase (Google OAuth, ES256 JWT via JWKS endpoint)
Database: Supabase PostgreSQL (pooler connection, port 5432)
Hosting:  Railway (two services from same GitHub repo)
Domain:   www.bahtzang.com (Squarespace DNS → Railway CNAME)
```

## Local Development

### Ports (from master-ports.md)
| Service  | Port |
|----------|------|
| Frontend | 3070 |
| Backend  | 4070 |

### Commands
```bash
npm run dev              # Run both frontend + backend concurrently
npm run dev:frontend     # Next.js on localhost:3070
npm run dev:backend      # FastAPI on localhost:4070
npm run install:frontend # npm install in /frontend
npm run install:backend  # pip install in /backend
npm test                 # Run all tests (backend + frontend)
npm run test:backend     # pytest (336 tests, ~4s)
npm run test:frontend    # Vitest (124 tests, ~3s)
npm run test:backend:cov # Backend with coverage report
```

### Environment Variables
- Backend: copy `backend/.env.example` → `backend/.env`
- Frontend: copy `frontend/.env.example` → `frontend/.env.local`

## Tech Stack

### Frontend (`/frontend`)
- Next.js 14 (App Router, `output: "standalone"` for Railway)
- React 18, TypeScript
- Tailwind CSS with semantic color tokens (light/dark theme via CSS custom properties)
- Recharts for charts
- Supabase JS (`getSupabase()` lazy singleton to avoid build-time crash)
- Most pages are `"use client"` — data fetched via `useApiQuery` hook or `useEffect` gated by auth
- Static pages (`about`, `changelog`, `roadmap`) are Server Components (zero JS shipped)
- Chart components (Recharts) lazy-loaded via `dynamic(() => import(...), { ssr: false })`
- Global focus-visible ring, prefers-reduced-motion, skip-to-content link
- Error boundary (`error.tsx`), custom 404 (`not-found.tsx`), loading state (`loading.tsx`)
- 15s fetch timeout via `AbortSignal.timeout()` on most API calls (45s for `runPlan` — Claude API is slow)

### Backend (`/backend`)
- Python FastAPI
- SQLAlchemy 2.0 (Mapped types, `get_db()` dependency injection)
- Anthropic SDK (Claude Sonnet for trading decisions)
- APScheduler (cron at 9:35 AM ET, Mon-Fri)
- PyJWT + JWKS (`PyJWKClient` fetches Supabase's ES256 public key)
- httpx for async HTTP (Schwab, Alpha Vantage)

## Key Patterns

### Auth Flow
```
Google → Supabase OAuth → Supabase JWT (ES256) → Bearer token in API requests
Backend verifies via JWKS endpoint: {SUPABASE_URL}/auth/v1/.well-known/jwks.json
ALLOWED_EMAIL accepts a single email or comma-separated list (case-insensitive, whitespace-tolerant) — shared access without full per-user data scoping
```

### Trading Pipeline (plans/executor.py)
```
Gather (Alpaca) → Earnings (Finnhub cache) → Branch on decision_mode → Coerce zero-value to hold → Validate (per-portfolio constraints) → Act (Alpaca) → Log (PostgreSQL)
  claude_decides:              Claude Sonnet generates all decisions (30s timeout, USAGE/HEADROOM block)
  rules_decide:                Strategy.generate_signals() only — Claude never called
  rules_with_claude_oversight: Strategy signals → per-decision Claude review → confirmed or overridden
Every decision logged — even holds and blocked trades
Alpaca SDK calls wrapped in asyncio.to_thread() to avoid blocking the event loop
Earnings data: position sizing reduced 50% at 0-1 days, 70% at 2 days before earnings
Pipeline types: Position, Quote, NewsItem, TradeDecision, CycleResult (pipeline_types.py)
Claude prompt includes a USAGE/HEADROOM block: total_invested vs max, orders_used_today vs limit, position slots, and effective_buy_ceiling = min(cash, max_single_trade, invest_headroom) — closes the information asymmetry that previously blocked trades at validation
Coerce-before-validate: qty<=0 or price<=0 → hold (with reason preserved in audit trail)
Oversight trades: rules_recommendation (JSON) on Trade stores strategy's original signal before Claude review
```

### Portfolios (plans/)
```
Every trade runs through a Portfolio (virtual sub-account). No global trader — the scheduler calls run_all_plans().
Each Portfolio has its own budget, virtual_cash, trading goal, risk profile, and is_active kill switch.
All portfolios share one Alpaca account — budget validation ensures SUM(budgets) <= real equity.
Per-portfolio asyncio locks prevent concurrent runs from double-spending virtual cash.
Budget validation uses pg_advisory_xact_lock for cross-process serialization.
Sell validation prevents cross-portfolio position theft (checks virtual positions, not Alpaca).
Per-trade atomic commits — each trade committed immediately after Alpaca order.
fetch_market_data() shared between scheduled runs and manual "Run Now".
Default portfolio created on first startup if table is empty (lifespan hook in main.py).
Circuit breaker RED level sets is_active=False on all portfolios (replaces global kill switch).
```

### Decision Modes
```
Each portfolio independently sets decision_mode (varchar, stored on Portfolio):
  claude_decides              — Claude Sonnet makes all trade decisions. Higher API cost, adapts to context.
  rules_decide                — Deterministic strategy only. Claude never called. Cheapest. Exactly replicates backtests.
  rules_with_claude_oversight — Strategy recommends; Claude reviews per-decision and may override.

strategy_id (varchar) and strategy_params (JSON) select the strategy and its parameters for rules modes.
STRATEGY_REGISTRY (app/strategies/registry.py) maps id → class; strategies are:
  sma_crossover, rsi_mean_reversion, buy_and_hold, dual_momentum

Oversight trades: rules_recommendation JSON column on Trade stores the strategy's original signal before Claude
review. Divergence (strategy action ≠ final action) is detected at read time from this column.
Mode changes logged in PortfolioStrategyAudit with old/new config snapshot.
GET /portfolios/{id}/oversight-activity returns confirmed/overridden summary stats + per-decision records.
```

### Frontend Auth Guard
Pages call `useAuth()` and only fetch data when `user` is truthy.
`AuthProvider` pushes token to API layer via `setApiToken()`.

## File Structure
```
backend/
  app/
    main.py           # App setup + router registration (65 lines)
    auth.py           # JWKS-based JWT verification, require_auth dependency
    config.py         # Pydantic Settings (all env vars)
    database.py       # SQLAlchemy engine + SessionLocal (pool_pre_ping=True)
    models.py         # Trade, PortfolioSnapshot + feature model imports
    routes/           # API route modules (feature-isolated)
      portfolio.py    # GET /portfolio, /portfolio/snapshots, /portfolio/metrics, POST /portfolio/snapshot
      trades.py       # GET /trades, GET /trades/summary (lightweight, no reasoning), GET /trades/export
      bot.py          # POST /run (rate-limited 2/min via slowapi), GET /bot/status (active/total portfolios)
      todos.py        # CRUD /admin/todos (JSON file persistence, asyncio.Lock)
    brokers/          # Broker abstraction layer
      base.py         # BrokerInterface ABC (typed: Position, AccountBalance)
      alpaca.py       # AlpacaBroker (async via to_thread, primary broker)
      schwab.py       # SchwabBroker (backup, shared httpx client for token + API)
    strategies/       # Shared strategy infrastructure (NOT a feature module — like analytics.py)
      __init__.py     # Re-exports: BaseStrategy, StrategySignal, STRATEGY_REGISTRY, all strategy classes
      base.py         # BaseStrategy ABC + StrategySignal dataclass
      registry.py     # STRATEGY_REGISTRY dict + get_strategy_info()
      sma_crossover.py     # SMACrossover (50/200 golden/death cross)
      rsi_mean_reversion.py # RSIMeanReversion (30/70 thresholds)
      buy_and_hold.py      # BuyAndHold (equal-weight day-1 benchmark)
      dual_momentum.py     # DualMomentum (Antonacci: SPY/VEU/BIL monthly rotation)
    backtest/         # Feature module: backtesting framework (Phase F)
      models.py       # BacktestConfig, BacktestResult, OHLCVCache tables
      data.py         # Alpaca OHLCV fetch + PostgreSQL cache with gap-fill
      engine.py       # Day-by-day simulation with lookahead bias prevention
      strategies.py   # Shim (deprecated): re-exports app.strategies.*; keeps PositionInfo + SimulationState
      routes.py       # CRUD /backtest + background run
    earnings/         # Feature module: earnings calendar (Phase F)
      models.py       # EarningsEvent table (Finnhub cache)
      client.py       # Finnhub API + DB cache + format_csv() + days_until_earnings()
      routes.py       # GET /earnings, POST /earnings/refresh
    plans/            # Feature module: portfolios (virtual sub-accounts)
      models.py       # Portfolio, Trade (plan_snapshots FK portfolio_id) tables
      constraints.py  # Per-portfolio trading constraints (cooldown, frequency cap, repeat-action guard)
      executor.py     # Per-portfolio trading cycle; asyncio locks; coerces qty<=0/price<=0 to hold; threads usage to Claude prompt; circuit breaker RED deactivates all portfolios
      routes.py       # CRUD + run + export at /portfolios/* (advisory lock budget validation, rate-limited)
      snapshots.py    # Daily snapshot capture for equity curves
    forex/            # Feature module: independent forex backtest tool (Phase F+)
      models.py       # ForexBar (OHLCV cache), ForexBacktestRun (config + results)
      zones.py        # 5-bar pivot detection + 0.5% single-linkage clustering → S/R zones
      patterns.py     # Bullish/bearish pin bar (2× wick / 0.5× opposing) + body-engulfing
      data.py         # yfinance fetch + DB cache (5-row tolerance) + W-FRI weekly resample
      engine.py       # Bar-by-bar simulator: bracket SL/TP, zone-break exit, optional progress/time_band early exits
      routes.py       # GET /forex/symbols, CRUD /forex/backtests with background runner
      cli.py          # Standalone runner: python -m app.forex.cli
    analytics.py      # Portfolio metrics: Sharpe, Sortino, drawdown, win rate, profit factor
    # strategies/ — see above; lives at app level, not inside a feature module
    pipeline_types.py # TypedDict definitions for pipeline data (Position, Quote, TradeDecision, etc.)
    claude_brain.py   # AsyncAnthropic → Claude Sonnet → CSV prompt (30s timeout) + earnings context
    circuit_breaker.py # 3-tier staged halts (YELLOW/ORANGE/RED) on portfolio P&L
    compliance.py     # PDT day trade tracking + wash sale 30-day cooling detection
    guardrails.py     # RISK_PRESETS, TRADING_GOALS, apply_risk_preset() — no DB state, no policy gate
    notifier.py       # Slack webhook notifications (fire-and-forget)
    position_sizing.py # Quarter-Kelly with confidence^2 + earnings proximity reduction
    sector_rotation.py # 11 sector ETFs relative strength vs SPY
    technical_analysis.py # pandas-ta indicators (RSI/MACD/BB/SMA/ATR) + Alpaca Data API
    decision_coercion.py # Shared helpers — coerce_zero_qty_to_hold + coerce_bad_price_to_hold; called by plan executor
    market_data.py    # Alpha Vantage news (quotes moved to Alpaca Data API)
    scheduler.py      # Trading frequency + daily snapshot (4:05 PM) + summary (4:10 PM) + earnings refresh (7 AM) — DB calls via to_thread()
    logger.py         # Trade logging to PostgreSQL
  data/
    todo-tasks.json   # Admin todo tasks (runtime, file-based)
  railway.toml        # Railway deploy config
  pytest.ini          # Test config (markers: unit, integration, e2e)
  tests/              # Test suites (336 backend tests)
    conftest.py       # SQLite in-memory + StaticPool, auth bypass, mock broker, test helpers
    plans/            # Portfolio model, executor, constraints, route, snapshot tests
    earnings/         # Earnings route integration tests
    forex/            # Forex zones, patterns, engine, data, routes, early-exit tests (53 tests)
    test_claude_brain_prompt.py  # USAGE/HEADROOM block in the Claude prompt
    test_zero_qty_coercion.py    # Coerce qty<=0 / price<=0 to hold + plan headroom plumbing
    test_allowed_emails.py       # CSV-parsed ALLOWED_EMAIL allow-list
    test_dual_momentum_strategy.py  # DualMomentum unit tests (12 tests)

frontend/
  src/
    app/              # Next.js App Router pages
      page.tsx        # / (dashboard)
      trades/         # /trades
      login/          # /login
      roadmap/        # /roadmap (anchor IDs for cross-linking)
      changelog/      # /changelog (stats header, cross-link badges)
      concepts/       # /concepts (tabbed: Strategic/SEO/Integrations/UX)
      about/          # /about
      status/         # /status
      docs/           # /docs
      analytics/      # /analytics
      backtest/       # /backtest (configure + run backtests, view results)
      earnings/       # /earnings (upcoming earnings calendar, color-coded proximity)
      portfolios/     # /portfolios (list + /portfolios/[id] detail + /portfolios/new)
      forex/          # /forex (independent swing-zone backtest UI — for non-engineer collaborator)
      testing/        # /testing (test inventory, execution cadence, 460 tests)
      audit-log/      # /audit-log
      todos/          # /todos (API-backed CRUD, category grouping)
      settings/       # /settings (timezone selector, display prefs; home for future notification prefs)
      markets/        # /markets (financial products reference: tradeable now, near-term, future)
      error.tsx       # Error boundary with retry
      loading.tsx     # Root loading spinner (Suspense fallback)
      not-found.tsx   # Custom 404 page
      providers.tsx   # ThemeProvider + AuthProvider + AppShell with TopNav + skip link
      layout.tsx      # Root layout (Server Component, anti-flash theme script, no painted bg so liquid-glass backdrop shows)
      globals.css     # Liquid-glass theme system: light/dark CSS-var palettes, vivid radial-gradient body backdrop, .bz-glass / .bz-glass-soft / .bz-glass-strong utilities, prefers-reduced-transparency fallback
    components/       # Reusable UI components
      TopNav.tsx      # Fixed top bar with mega-menu (Core/Trading/Forex/Admin); replaces Sidebar.tsx
      CrossLink.tsx   # Reusable cross-link badge (pill-shaped, color-coded by type)
      KillSwitchButton.tsx # Kill switch with activate + deactivate
    lib/
      api.ts          # fetchAPI with Bearer token, 15s timeout (45s for runPlan), admin todo CRUD
      constants.ts    # Shared constants (GOAL_CONFIG — single source of truth for trading goals)
      auth.tsx        # AuthProvider, useAuth hook
      theme.tsx       # ThemeProvider, useTheme hook (light/dark, localStorage)
      supabase.ts     # Lazy Supabase client singleton
      types.ts        # TypeScript interfaces
      utils.ts        # formatCurrency, formatDateTime
      useHashScroll.ts # (removed — replaced by HashScroll.tsx component)
      useApiQuery.ts  # Reusable data-fetching hook (loading + error state)
    data/             # Static data (roadmap, changelog, concepts)
  railway.toml        # Railway deploy config (HOSTNAME=0.0.0.0)
```

## Railway Deployment Notes
- Backend root directory: `/backend`
- Frontend root directory: `/frontend`
- Frontend needs `HOSTNAME=0.0.0.0` env var (Next.js standalone binds to container hostname otherwise)
- Frontend start command copies `.next/static` into standalone dir
- Supabase DB: use pooler connection string (port 5432, `pooler.supabase.com`)
- Direct connection (`db.*.supabase.co`) does NOT work from Railway (IPv6 unreachable)

## Conventions

### Design System
- Light/dark theme toggle — persisted in localStorage, respects system preference
- Liquid Glass design system: vivid radial-gradient body backdrop + frosted-glass cards via `.bz-glass` / `.bz-glass-soft` / `.bz-glass-strong` utility classes; `prefers-reduced-transparency` swaps to solid surfaces
- Light theme uses white tint over pastel backdrop; dark theme uses NAVY tint over saturated dark backdrop (white at low alpha disappears over dark — see `docs/solutions/ui-bugs/`)
- Semantic color tokens via CSS custom properties: `bg-card`, `bg-card-alt`, `text-primary`, `text-secondary`, `text-muted`, `border-border`, `text-accent`, `text-pos`, `text-neg`, `bg-pos`, `bg-neg`, `bg-accent-2`
- Top-bar mega-menu navigation (TopNav.tsx) — Core / Trading / Forex / Admin groups
- Never use hardcoded zinc-*/slate-* for theme colors — use semantic tokens or `.bz-glass*` utilities
- Body must remain the painted layer behind glass cards — don't paint a background-color on `<main>`, wrappers, or anything between body and `.bz-glass`

### Code Patterns
- All API calls go through `fetchAPI()` in `lib/api.ts`
- Auth gating: `if (!user) return;` at top of `useEffect` in every page
- Per-portfolio kill switch: `PATCH /portfolios/{id}` with `{ is_active: false }` pauses that portfolio
- Risk presets (conservative/moderate/aggressive) in guardrails.py — applied at portfolio creation/update
- Rate limiting: slowapi (2/min on /run and /portfolios/{id}/run, 60/min global default)
- Trade logging: every cycle logs to `trades` table regardless of outcome
- Scheduler derives trading frequency from `max(active portfolios' trading_frequency)`

### Testing
- Backend: pytest + SQLite in-memory (StaticPool) + FastAPI TestClient
- Frontend: Vitest + @testing-library/react + jsdom
- 460 total tests (336 backend + 124 frontend), ~9s full suite
- Test helpers: `make_plan()`, `make_trade()` in `tests/conftest.py`
- Budget validation stubbed in integration tests (pg_advisory_xact_lock is PostgreSQL-only)
- Scheduler patched out in TestClient fixture (prevents SchedulerAlreadyRunningError)
- Recharts mocked in component tests (jsdom lacks SVG rendering)
- Pre-commit hook runs tsc + eslint + pytest + vitest on every commit (~5s)
- GitHub Actions CI on push/PR to main
- Slash commands: `/test-run`, `/test-new <feature>`, `/test-audit`, `/doc`

### Feature Module Isolation
New features go in their own Python packages under `backend/app/`:
- Each module has its own `models.py`, business logic, and `routes.py`
- Models imported in root `models.py` so `create_all()` picks them up
- Router registered in `main.py` with a single `include_router()` line
- Integration with the trading pipeline kept to minimal touchpoints
- Example: `backtest/` and `earnings/` are fully self-contained packages

**Shared infrastructure (not feature modules):** Code used by multiple features lives at the `app/` level, not inside a feature module. Examples: `analytics.py`, `pipeline_types.py`, `strategies/`. Do not import from a feature module to serve another feature — that is an isolation violation. If the live executor needs strategies, import from `app.strategies`, not `app.backtest.strategies`.

---

## Behavioral Rules

### Core: How to Answer (Universal)

1. **No flattery.** Skip "great question," "you're absolutely right," "fascinating perspective" and every variant. Start with substance.

2. **Lead with the strongest counterargument before agreeing.** If I state a position, steelman the opposing view first — even if you ultimately agree.

3. **Don't capitulate under pushback.** If I push back without new evidence or better reasoning, restate your position. Caving when you were right is worse than disagreeing.

4. **State confidence on non-trivial claims:** HIGH / MODERATE / LOW / UNKNOWN. Distinguish three sources:
   - "I know this" (training data, verifiable)
   - "I'm reasoning from principles" (inference)
   - "I'm guessing" (low signal)

5. **Say "I don't know" when you don't.** Never invent citations, dates, numbers, API behaviors, library versions, regulations, or competitor facts. If unsure, flag it and tell me how to verify.

6. **Generate your own estimates before reacting to mine.** Don't anchor.

7. **Never apologize for disagreeing.** Accuracy > my approval.

8. **If my question contains a faulty premise, fix the premise first.** Don't answer a bad question well.

9. **Surface my implicit assumptions.** Call out sunk-cost reasoning when I'm defending past decisions vs. assessing fresh.

10. **Articulate tradeoffs, not preferences.** Show the chain: X because Y, given Z. "A beats B for [reason], but B wins if [condition]."

11. **Default to the simpler/cheaper/less-built option when it suffices.**

12. **Recency:** your training data may be stale. For anything that changes — regulations, prices, APIs, vendor specs, current events — flag it and tell me what to verify with a live source.

13. **No moral/ethical disclaimers unless I ask.** Detailed is fine; padded is not.

### Memory Loop

When you notice a pattern, preference, decision, or piece of context that should persist beyond this conversation, say so explicitly and offer to draft a context-doc update. Treat yourself as a co-maintainer of this project's memory, not a passive consumer of it. Flag inconsistencies between what I'm saying now and what's in project knowledge.

### Project Context

**WHO I AM:** James Chang. Non-technical but product-sharp. Strong instinct for strategy and risk decisions; relies on Claude for all implementation. Reviews outcomes not diffs — flag failure modes in plain language before suggesting changes. Has been building this project over several months with AI assistance throughout.

**WHAT WE'RE BUILDING / WORKING ON:** bahtzang-trader — an AI-powered paper trading experiment where Claude Sonnet makes buy/sell/hold decisions on a live Alpaca paper account. The system has a FastAPI backend, a Next.js 14 dashboard, and Supabase for auth and PostgreSQL. Trades run through virtual "portfolio" sub-accounts with independent budgets, goals, risk profiles, and kill switches. The current stage is paper-trading: accumulating 30+ trades with zero losing weeks to qualify for the Phase G live switch ($200 real capital, graduated scale-up). No real money is at risk yet. The project is a personal experiment — not a product for external users.

**DOMAIN-SPECIFIC CAUTION:**
- **CODE:** I review diffs but rely on Claude for implementation. Flag failure modes and edge cases *before* suggesting changes, not after. If you're about to assume a library behavior or API contract, verify it or say so — don't silently guess.
- **FINANCIAL/TRADING:** Push back hard on weak reasoning about strategy, position sizing, or risk. The Phase G transition plan is already designed and locked — don't propose live-trading changes without being asked. When touching PDT rules, wash-sale rules, or Alpaca API rate limits, cite the actual constraint and flag whether it needs live verification.
- **SCOPE CREEP:** Default to the minimal change. This project has a narrow active goal (accumulate paper trades). Features that don't serve that gate are low priority unless James explicitly asks for them.

**DECISIONS ALREADY MADE — DO NOT RE-LITIGATE:**
- **Phase G live allocation is $200.** Intentionally small for the first live run. Can scale via ≤2.5× raises after 3 months at Stage 4 without restarting graduation.
- **Phase G gate requires zero losing weeks during paper trading** (stricter than win-rate ≥ 50%). A losing paper week means the strategy is wrong, not the gates are too tight.
- **Rollback = kill switch + manual unwind.** No auto-downgrade to paper trading. Human in the loop on rollback.
- **No manual per-trade approval in Stage 1.** Bridge-gate review at end of each window is the human checkpoint.
- **Portfolio-only execution model.** The global trader is gone. Every trade runs through a Portfolio. Do not re-introduce a global execution path.
- **Forex tool is deliberately siloed.** It's a sandbox for a friend's strategy (Nick Shawn). Don't extend or integrate it into the main trading pipeline without a proven edge.
- **460 tests are the baseline.** Don't ship features that drop the count or break CI.

(If a new fact or argument genuinely challenges one of these, say so directly. Otherwise, build on them.)

**TONE:** Direct and decision-oriented. Short responses by default — expand only when the complexity warrants it. No summaries of what you just did. No unsolicited cleanup or refactoring. When something is uncertain, say so and name the uncertainty precisely.
