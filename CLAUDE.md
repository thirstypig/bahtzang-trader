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
Gather (Schwab) → Think (Claude) → Validate (guardrails) → Act (Schwab) → Log (PostgreSQL)
Every decision logged — even holds and blocked trades
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
    models.py         # Trade model (11 columns + 2 indexes)
    routes/           # API route modules (feature-isolated)
      portfolio.py    # GET /portfolio (uses BrokerInterface)
      trades.py       # GET /trades
      guardrails.py   # GET/POST /guardrails, POST /killswitch
      bot.py          # POST /run
    brokers/          # Broker abstraction layer
      base.py         # BrokerInterface ABC (get_positions, get_balance, place_order)
      schwab.py       # SchwabBroker (token cache with expiry, shared httpx client)
    claude_brain.py   # AsyncAnthropic → Claude Sonnet → JSON decision
    guardrails.py     # GuardrailsUpdate Pydantic model + policy gate
    trade_executor.py # Pipeline orchestrator (asyncio.gather, Lock, BrokerInterface)
    market_data.py    # Alpha Vantage quotes + news (shared httpx, parallel fetch)
    scheduler.py      # APScheduler cron (9:35 AM ET, Mon-Fri)
    logger.py         # Trade logging to PostgreSQL
  guardrails.json     # Runtime config (editable via API)
  railway.toml        # Railway deploy config

frontend/
  src/
    app/              # Next.js App Router pages
      page.tsx        # / (dashboard)
      trades/         # /trades
      settings/       # /settings
      login/          # /login
      roadmap/        # /roadmap
      changelog/      # /changelog
      about/          # /about
      status/         # /status
      docs/           # /docs
      analytics/      # /analytics
      audit-log/      # /audit-log
      todos/          # /todos
      providers.tsx   # AuthProvider + AppShell (conditional Navbar)
      layout.tsx      # Root layout (Server Component, no "use client")
    components/       # Reusable UI components
    lib/
      api.ts          # fetchAPI with Bearer token from setApiToken()
      auth.tsx        # AuthProvider, useAuth hook
      supabase.ts     # Lazy Supabase client singleton
      types.ts        # TypeScript interfaces
      utils.ts        # formatCurrency, formatDateTime
    data/             # Static data (roadmap, changelog, todos)
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
- Guardrails editable via JSON file on backend, API endpoints to read/write
- Trade logging: every cycle logs to `trades` table regardless of outcome
