# CLAUDE.md — bahtzang-trader

## Project Overview
AI-powered trading experiment. Claude Sonnet makes buy/sell/hold decisions; a Next.js dashboard displays results; a FastAPI backend handles execution against Alpaca paper-trading. No real money at risk during paper phase.

## Architecture
```
Monorepo: /frontend (Next.js 14) + /backend (Python FastAPI)
Auth:     Supabase (Google OAuth, ES256 JWT via JWKS endpoint)
Database: Supabase PostgreSQL (pooler connection, port 5432)
Hosting:  Railway (two services from same GitHub repo)
Domain:   www.bahtzang.com (Squarespace DNS → Railway CNAME)
```

## Local Development

### Ports
| Service  | Port |
|----------|------|
| Frontend | 3070 |
| Backend  | 4070 |

### Commands
```bash
npm run dev              # Run both frontend + backend concurrently
npm run dev:frontend     # Next.js on localhost:3070
npm run dev:backend      # FastAPI on localhost:4070
npm run test             # All tests (backend + frontend)
npm run test:frontend    # Vitest (~3s)
npm run test:backend     # pytest (~4s)
```

### Environment Variables
- Backend: copy `backend/.env.example` → `backend/.env`
- Frontend: copy `frontend/.env.example` → `frontend/.env.local`

## Tech Stack

### Frontend (`/frontend`)
- Next.js 14 (App Router, `output: "standalone"` for Railway)
- React 18, TypeScript, Tailwind CSS (semantic CSS-var tokens)
- Recharts (lazy-loaded via `dynamic(..., { ssr: false })`)
- Supabase JS (`getSupabase()` lazy singleton)
- Liquid-glass design system: `.bz-glass` / `.bz-glass-soft` / `.bz-glass-strong` on frosted cards

### Backend (`/backend`)
- Python FastAPI
- SQLAlchemy 2.0 (Mapped types, `get_db()` dependency injection)
- Anthropic SDK (Claude Sonnet for trade decisions)
- APScheduler (cron at 9:35 AM ET, Mon-Fri)
- PyJWT + JWKS (`PyJWKClient` fetches Supabase's ES256 public key)

## Key Patterns

### Auth Flow
```
Google → Supabase OAuth → Supabase JWT (ES256) → Bearer token in API requests
Backend verifies via JWKS endpoint: {SUPABASE_URL}/auth/v1/.well-known/jwks.json
ALLOWED_EMAIL accepts a single email or comma-separated list (multi-user shared access)
```

### Trading Pipeline (plans/executor.py)
```
Gather (Alpaca) → Earnings (Finnhub cache) → Branch on decision_mode → Coerce zero-value to hold → Validate (per-portfolio constraints) → Act (Alpaca) → Log (PostgreSQL)
  claude_decides:              Claude Sonnet generates decisions (30s timeout)
  rules_decide:                Strategy only — Claude never called (matches backtests exactly)
  rules_with_claude_oversight: Strategy recommends → Claude reviews each decision → confirmed or overridden
Every decision logged — even holds and blocked trades
Coerce-before-validate: qty<=0 or price<=0 → hold (with reason in audit trail)
Oversight trades store the strategy's original signal in rules_recommendation (JSON) on Trade
```

### Portfolios (plans/)
```
Every trade runs through a Portfolio (virtual sub-account). No global trader.
Each Portfolio has its own budget, virtual_cash, trading goal, risk profile, is_active kill switch,
  decision_mode, strategy_id, and strategy_params.
All portfolios share one Alpaca account — budget validation ensures SUM(budgets) <= real equity.
Per-portfolio asyncio locks prevent concurrent double-spending.
Budget validation uses pg_advisory_xact_lock for cross-process serialization.
Circuit breaker RED level sets is_active=False on all portfolios.
```

### Decision Modes
```
claude_decides              — AI-only, adapts to context, highest API cost
rules_decide                — deterministic strategy, cheapest, exactly replicates backtests
rules_with_claude_oversight — strategy recommends, Claude reviews & may override per decision

Strategies (app/strategies/): sma_crossover, rsi_mean_reversion, buy_and_hold, dual_momentum
GET /portfolios/{id}/oversight-activity returns confirmed/overridden breakdown
```

### Frontend Auth Guard
Pages call `useAuth()` and only fetch data when `user` is truthy.
`AuthProvider` pushes token to API layer via `setApiToken()`.

## File Structure
```
backend/
  app/
    main.py           # App setup + router registration
    auth.py           # JWKS-based JWT verification, require_auth dependency
    config.py         # Pydantic Settings (all env vars)
    database.py       # SQLAlchemy engine + SessionLocal (pool_pre_ping=True)
    models.py         # Trade, PortfolioSnapshot + feature model imports
    routes/           # API route modules (feature-isolated)
      portfolio.py    # GET /portfolio, /portfolio/snapshots, /portfolio/metrics
      trades.py       # GET /trades, GET /trades/summary, GET /trades/export
      bot.py          # POST /run (rate-limited), GET /bot/status
      todos.py        # CRUD /admin/todos (JSON file persistence)
    brokers/          # Broker abstraction layer
      base.py         # BrokerInterface ABC
      alpaca.py       # AlpacaBroker (async via to_thread, primary broker)
      schwab.py       # SchwabBroker (backup)
    strategies/       # Shared strategy infrastructure (NOT a feature module)
      __init__.py     # Re-exports: BaseStrategy, StrategySignal, STRATEGY_REGISTRY
      base.py         # BaseStrategy ABC + StrategySignal dataclass
      registry.py     # STRATEGY_REGISTRY dict + get_strategy_info()
      sma_crossover.py / rsi_mean_reversion.py / buy_and_hold.py / dual_momentum.py
    backtest/         # Feature module: backtesting framework
      models.py / data.py / engine.py / routes.py
    earnings/         # Feature module: earnings calendar (Finnhub cache)
      models.py / client.py / routes.py
    plans/            # Feature module: portfolios (virtual sub-accounts)
      models.py       # Portfolio, PlanSnapshot, PortfolioStrategyAudit
      executor.py     # Per-portfolio trading cycle; decision_mode branching
      routes.py       # CRUD + run + export + oversight-activity at /portfolios/*
      constraints.py  # Cooldown, frequency cap, repeat-action guard
    forex/            # Feature module: independent forex backtest tool (for Nick Shawn)
    analytics.py      # Portfolio metrics: Sharpe, Sortino, drawdown, win rate
    pipeline_types.py # TypedDict definitions (Position, Quote, TradeDecision, etc.)
    claude_brain.py   # AsyncAnthropic → Claude Sonnet + review_trade_decision()
    circuit_breaker.py # 3-tier staged halts (YELLOW/ORANGE/RED)
    compliance.py     # PDT day trade tracking + wash sale detection
    notifier.py       # Slack webhook notifications
    position_sizing.py # Quarter-Kelly + earnings proximity reduction
    technical_analysis.py # pandas-ta indicators + Alpaca Data API
    scheduler.py      # APScheduler: trading + snapshots + earnings refresh
    decision_coercion.py # coerce_zero_qty_to_hold + coerce_bad_price_to_hold
  data/
    todo-tasks.json   # Admin todo tasks (runtime, file-based)
  railway.toml        # Railway deploy config

frontend/
  src/
    app/              # Next.js App Router pages
      page.tsx        # / (dashboard)
      portfolios/     # /portfolios + /portfolios/[id] + /portfolios/new
                      # /portfolios/[id]/strategy (Decision Engine)
                      # /portfolios/[id]/oversight (Oversight Activity)
      trades/backtest/earnings/analytics/forex/
      settings/markets/roadmap/changelog/concepts/about/docs/testing/audit-log/todos/
    components/       # Reusable UI components
      TopNav.tsx      # Fixed top bar + mega-menu (Core/Trading/Forex/Admin)
      DecisionModeBadge.tsx # Badge for claude_decides / rules_decide / hybrid
      PortfolioAllocationChart.tsx / TradeTable.tsx / PortfolioEquityCurve.tsx
    lib/
      api.ts          # fetchAPI with Bearer token, 15s timeout (45s for runPlan)
      types.ts        # TypeScript interfaces
      auth.tsx / theme.tsx / supabase.ts / utils.ts / useApiQuery.ts
    data/             # Static data (roadmap, changelog, concepts)
  railway.toml        # Railway deploy config (HOSTNAME=0.0.0.0)
```

## Conventions

### Design System
- Liquid-glass design: vivid radial-gradient body backdrop + frosted `.bz-glass` cards
- Semantic CSS tokens: `bg-card`, `text-primary`, `text-muted`, `border-border`, `text-accent`, `text-pos`, `text-neg`
- Never use hardcoded zinc-*/slate-* for theme colors
- Top-bar mega-menu navigation (Core / Trading / Forex / Admin groups)

### Code Patterns
- All API calls go through `fetchAPI()` in `lib/api.ts`
- Auth gating: `if (!user) return;` at top of `useEffect` in every page
- Per-portfolio kill switch: `PATCH /portfolios/{id}` with `{ is_active: false }`
- Rate limiting: slowapi (2/min on /run and portfolio run endpoints)
- Trade logging: every cycle logs to `trades` table regardless of outcome

### Testing
- 418+ total tests (backend pytest + frontend Vitest)
- Pre-commit hook runs tsc + eslint + pytest + vitest on every commit
- Recharts mocked in component tests (jsdom lacks SVG rendering)
