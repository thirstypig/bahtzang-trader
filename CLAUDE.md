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
- All pages are `"use client"` — data fetched via `useEffect` gated by auth

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
Gather (Alpaca) → Think (Claude, 30s timeout) → Validate (guardrails) → Act (Alpaca) → Log (PostgreSQL)
Every decision logged — even holds and blocked trades
Alpaca SDK calls wrapped in asyncio.to_thread() to avoid blocking the event loop
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
    models.py         # Trade, GuardrailsConfig, GuardrailsAudit models
    routes/           # API route modules (feature-isolated)
      portfolio.py    # GET /portfolio (uses BrokerInterface)
      trades.py       # GET /trades
      guardrails.py   # GET/POST /guardrails, POST /killswitch, POST /killswitch/deactivate
      bot.py          # POST /run (rate-limited 2/min via slowapi)
      todos.py        # CRUD /admin/todos (JSON file persistence, asyncio.Lock)
    brokers/          # Broker abstraction layer
      base.py         # BrokerInterface ABC (get_positions, get_balance, place_order)
      alpaca.py       # AlpacaBroker (async via to_thread, primary broker)
      schwab.py       # SchwabBroker (backup, optional credentials)
    claude_brain.py   # AsyncAnthropic → Claude Sonnet → JSON decision (30s timeout)
    guardrails.py     # GuardrailsUpdate Pydantic model + policy gate (DB-backed)
    notifier.py       # Slack webhook notifications (fire-and-forget)
    trade_executor.py # Pipeline orchestrator (asyncio.gather, Lock, BrokerInterface)
    market_data.py    # Alpha Vantage quotes + news (shared httpx, parallel fetch)
    scheduler.py      # APScheduler dynamic frequency (1x/3x/5x) + daily summary
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
- Kill switch: activate via POST /killswitch, deactivate via POST /killswitch/deactivate
- Rate limiting: slowapi (2/min on /run, 60/min global default)
- Trade logging: every cycle logs to `trades` table regardless of outcome
