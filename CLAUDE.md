# CLAUDE.md — bahtzang-trader

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
| Frontend | 3060 |
| Backend  | 4060 |

### Commands
```bash
npm run dev              # Run both frontend + backend concurrently
npm run dev:frontend     # Next.js on localhost:3060
npm run dev:backend      # FastAPI on localhost:4060
npm run install:frontend # npm install in /frontend
npm run install:backend  # pip install in /backend
```

### Environment Variables
- Backend: copy `backend/.env.example` → `backend/.env`
- Frontend: copy `frontend/.env.example` → `frontend/.env.local`

## Tech Stack

### Frontend (`/frontend`)
- Next.js 14 (App Router, `output: "standalone"` for Railway)
- React 18, TypeScript
- Tailwind CSS (dark theme, zinc-950 background)
- Recharts for charts
- Supabase JS (`getSupabase()` lazy singleton to avoid build-time crash)
- Most pages are `"use client"` — data fetched via `useApiQuery` hook or `useEffect` gated by auth
- Static pages (`about`, `docs`) are server components (no `"use client"`)

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
Only ALLOWED_EMAIL can access (single-user app)
```

### Trading Pipeline (trade_executor.py)
```
Gather (Alpaca) → Earnings (Finnhub cache) → Think (Claude, 30s timeout) → Validate (guardrails) → Act (Alpaca) → Log (PostgreSQL)
Every decision logged — even holds and blocked trades
Alpaca SDK calls wrapped in asyncio.to_thread() to avoid blocking the event loop
Earnings data: position sizing reduced 50% at 0-1 days, 70% at 2 days before earnings
Pipeline types: Position, Quote, NewsItem, TradeDecision, CycleResult (pipeline_types.py)
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
    models.py         # Trade, PortfolioSnapshot, GuardrailsConfig, GuardrailsAudit + feature model imports
    routes/           # API route modules (feature-isolated)
      portfolio.py    # GET /portfolio, /portfolio/snapshots, /portfolio/metrics, POST /portfolio/snapshot
      trades.py       # GET /trades
      guardrails.py   # GET/POST /guardrails, POST /killswitch, POST /killswitch/deactivate
      bot.py          # POST /run (rate-limited 2/min via slowapi)
      todos.py        # CRUD /admin/todos (JSON file persistence, asyncio.Lock)
    brokers/          # Broker abstraction layer
      base.py         # BrokerInterface ABC (typed: Position, AccountBalance)
      alpaca.py       # AlpacaBroker (async via to_thread, primary broker)
      schwab.py       # SchwabBroker (backup, shared httpx client for token + API)
    backtest/         # Feature module: backtesting framework (Phase F)
      models.py       # BacktestConfig, BacktestResult, OHLCVCache tables
      data.py         # Alpaca OHLCV fetch + PostgreSQL cache with gap-fill
      engine.py       # Day-by-day simulation with lookahead bias prevention
      strategies.py   # BaseStrategy + SMA Crossover, RSI Mean Reversion, Buy & Hold
      routes.py       # CRUD /backtest + background run
    earnings/         # Feature module: earnings calendar (Phase F)
      models.py       # EarningsEvent table (Finnhub cache)
      client.py       # Finnhub API + DB cache + format_csv() + days_until_earnings()
      routes.py       # GET /earnings, POST /earnings/refresh
    analytics.py      # Portfolio metrics: Sharpe, Sortino, drawdown, win rate, profit factor
    pipeline_types.py # TypedDict definitions for pipeline data (Position, Quote, TradeDecision, etc.)
    claude_brain.py   # AsyncAnthropic → Claude Sonnet → CSV prompt (30s timeout) + earnings context
    circuit_breaker.py # 3-tier staged halts (YELLOW/ORANGE/RED) on portfolio P&L
    compliance.py     # PDT day trade tracking + wash sale 30-day cooling detection
    guardrails.py     # GuardrailsUpdate Pydantic model + policy gate (DB-backed) + stop-loss enforcement
    notifier.py       # Slack webhook notifications (fire-and-forget)
    position_sizing.py # Quarter-Kelly with confidence^2 + earnings proximity reduction
    sector_rotation.py # 11 sector ETFs relative strength vs SPY
    technical_analysis.py # pandas-ta indicators (RSI/MACD/BB/SMA/ATR) + Alpaca Data API
    trade_executor.py # Pipeline: gather → indicators → earnings → think → validate → act → log → notify
    market_data.py    # Alpha Vantage news (quotes moved to Alpaca Data API)
    scheduler.py      # Trading frequency + daily snapshot (4:05 PM) + summary (4:10 PM) + earnings refresh (7 AM) — DB calls via to_thread()
    logger.py         # Trade logging to PostgreSQL
  data/
    todo-tasks.json   # Admin todo tasks (runtime, file-based)
  guardrails.json     # Default config (runtime config is in PostgreSQL)
  railway.toml        # Railway deploy config

frontend/
  src/
    app/              # Next.js App Router pages
      page.tsx        # / (dashboard)
      trades/         # /trades
      settings/       # /settings
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
      audit-log/      # /audit-log
      todos/          # /todos (API-backed CRUD, category grouping)
      providers.tsx   # AuthProvider + AppShell (conditional Navbar)
      layout.tsx      # Root layout (Server Component, no "use client")
    components/       # Reusable UI components
      AdminNav.tsx    # Shared admin page navigation (Todo|Roadmap|Concepts|Changelog)
      CrossLink.tsx   # Reusable cross-link badge (pill-shaped, color-coded by type)
      KillSwitchButton.tsx # Kill switch with activate + deactivate
    lib/
      api.ts          # fetchAPI with Bearer token + admin todo CRUD functions
      auth.tsx        # AuthProvider, useAuth hook
      supabase.ts     # Lazy Supabase client singleton
      types.ts        # TypeScript interfaces
      utils.ts        # formatCurrency, formatDateTime
      useHashScroll.ts # Scroll-to-anchor hook for cross-page linking
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
- Dark theme: zinc-950 background, zinc-900 cards, emerald-400 accents
- All API calls go through `fetchAPI()` in `lib/api.ts`
- Auth gating: `if (!user) return;` at top of `useEffect` in every page
- Guardrails stored in PostgreSQL (persists across Railway deploys), API endpoints to read/write
- Guardrails audit log: every config change logged with user, timestamp, and changes
- Stop-loss enforcement: blocks buys on positions below threshold, warns on holds
- Risk presets scale to actual portfolio value (from latest PortfolioSnapshot, fallback 100k)
- Kill switch: activate via POST /killswitch, deactivate via POST /killswitch/deactivate
- Rate limiting: slowapi (2/min on /run, 60/min global default)
- Trade logging: every cycle logs to `trades` table regardless of outcome

### Feature Module Isolation
New features go in their own Python packages under `backend/app/`:
- Each module has its own `models.py`, business logic, and `routes.py`
- Models imported in root `models.py` so `create_all()` picks them up
- Router registered in `main.py` with a single `include_router()` line
- Integration with the trading pipeline kept to minimal touchpoints
- Example: `backtest/` and `earnings/` are fully self-contained packages
