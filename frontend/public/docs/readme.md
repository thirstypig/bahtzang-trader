# bahtzang-trader

AI-powered trading bot that uses Claude Sonnet to make buy/sell/hold decisions. Next.js dashboard (light/dark theme) with portfolio tracking, trade history, backtesting, earnings calendar, and guardrail controls.

**Live at:** [www.bahtzang.com](https://www.bahtzang.com)

## Architecture

```
┌─────────────────────────────────┐
│  Next.js 14 Frontend (Railway)  │  www.bahtzang.com
│  Dashboard · Trades · Analytics  │  22 pages + login
│  Backtest · Earnings · Settings │
└──────────────┬──────────────────┘
               │ REST API + Bearer JWT
┌──────────────┴──────────────────┐
│  FastAPI Backend (Railway)      │  bahtzang-backend-production.up.railway.app
│  routes/ · brokers/ · services  │
│  Claude Brain · Guardrails      │
└──────┬────────┬────────┬────────┘
       │        │        │
  ┌────┴──┐ ┌───┴───┐ ┌──┴────────┐
  │Schwab │ │Alpha  │ │ Supabase  │
  │Alpaca │ │Vantage│ │ PostgreSQL│
  └───────┘ └───────┘ └───────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, Recharts |
| Backend | Python FastAPI, SQLAlchemy 2.0, APScheduler |
| AI | Claude Sonnet (Anthropic API) |
| Auth | Supabase (Google OAuth, ES256 JWT via JWKS) |
| Database | Supabase PostgreSQL |
| Hosting | Railway (2 services from monorepo) |
| Domain | www.bahtzang.com (Squarespace DNS → Railway) |

## Project Structure

```
bahtzang-trader/
├── frontend/                # Next.js 14 (App Router)
│   └── src/
│       ├── app/             # 22 pages (dashboard, trades, analytics, plans, backtest, etc.)
│       ├── components/      # Reusable UI (Sidebar, ThemeToggle, charts, etc.)
│       ├── lib/             # API client, auth, theme, sidebar, Supabase, types
│       └── data/            # Static data (roadmap, changelog, concepts)
├── backend/                 # Python FastAPI
│   └── app/
│       ├── main.py          # App setup + router registration + rate limiting
│       ├── routes/          # API route modules (portfolio, trades, guardrails, bot, todos)
│       ├── brokers/         # Broker abstraction (base.py + alpaca.py + schwab.py)
│       ├── auth.py          # Supabase JWT verification via JWKS
│       ├── backtest/         # Backtesting framework (3 strategies, OHLCV cache)
│       ├── earnings/         # Earnings calendar (Finnhub API cache, position sizing)
│       ├── plans/            # Investment Plans (routes, models, snapshots)
│       ├── claude_brain.py  # AI decision engine (AsyncAnthropic, 30s timeout)
│       ├── guardrails.py    # Safety limits + kill switch + stop-loss (stored in PostgreSQL)
│       ├── compliance.py    # PDT tracking + wash sale detection
│       ├── circuit_breaker.py # 3-tier circuit breakers (YELLOW/ORANGE/RED)
│       ├── position_sizing.py # Quarter-Kelly position sizing
│       ├── technical_analysis.py # pandas-ta indicators (RSI, MACD, BBands, SMA, ATR)
│       ├── sector_rotation.py # 11 sector ETFs vs SPY (LEADING/LAGGING)
│       ├── pipeline_types.py # TypedDict definitions (Position, Quote, TradeDecision, etc.)
│       ├── trade_executor.py # Pipeline: gather → think → validate → act → log
│       ├── market_data.py   # Alpha Vantage news sentiment
│       └── scheduler.py     # Dynamic frequency (1x/3x/5x) + snapshots + earnings refresh
│   └── data/
│       └── todo-tasks.json  # Admin todo tasks (runtime, file-based)
├── docs/plans/              # Architecture roadmap + feature plans
├── todos/                   # Code review findings (59 items)
├── CLAUDE.md                # Project conventions for Claude Code
└── package.json             # Root scripts (npm run dev)
```

## Pages

| Page | Description |
|------|------------|
| `/` | Dashboard — portfolio summary, Claude's decisions, equity curve |
| `/trades` | Trade history with sortable columns and full reasoning |
| `/settings` | Risk profiles, trading goals, guardrails, kill switch, manual trigger |
| `/analytics` | Sharpe, Sortino, drawdown, win rate, profit factor, equity vs SPY |
| `/plans` | Investment Plans — independent pie-style portfolio slices |
| `/plans/new` | Create a new plan with budget, goal, and timeline |
| `/plans/[id]` | Plan detail — positions, equity curve, trades, run/pause |
| `/backtest` | Backtest strategies (SMA Crossover, RSI Mean Reversion, Buy & Hold) |
| `/earnings` | Upcoming earnings calendar with position sizing integration |
| `/audit-log` | Guardrails config change audit trail |
| `/todos` | API-backed task tracker — categories, progress bars, CRUD |
| `/roadmap` | Kanban board — planned / in-progress / done |
| `/changelog` | Version history with feat/fix/security badges |
| `/concepts` | Ideas and explorations across 4 categories |
| `/errors` | Error log with ERR-XXXXXX reference codes |
| `/status` | Live service health checks |
| `/about` | Architecture diagram, tech stack, design philosophy |
| `/docs` | Daily operations guide, project docs, external links |
| `/login` | Google Sign-In via Supabase |

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+

### Installation

```bash
npm run install:frontend
npm run install:backend
```

### Environment Variables

Copy the example files and fill in your keys:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

### Development

```bash
npm run dev              # Both services concurrently
npm run dev:frontend     # http://localhost:3060
npm run dev:backend      # http://localhost:4060
```

### Ports

| Service | Port |
|---------|------|
| Frontend | 3060 |
| Backend API | 4060 |

## API Documentation

- **Local:** [http://localhost:4060/docs](http://localhost:4060/docs)
- **Production:** [https://bahtzang-backend-production.up.railway.app/docs](https://bahtzang-backend-production.up.railway.app/docs)

## Trading Pipeline

Every cycle (configurable 1x/3x/5x per day, or manual trigger):

1. **Gather** — fetch portfolio + balances from Alpaca, technical indicators (RSI/MACD/BBands/SMA/ATR), sector rotation signals, earnings calendar
2. **Think** — send context to Claude Sonnet, get buy/sell/hold decision (30s timeout)
3. **Validate** — run decision through guardrails (kill switch, stop-loss, limits, daily cap, position count, PDT compliance)
4. **Act** — execute order on Alpaca if approved, with earnings-aware position sizing
5. **Log** — write decision + reasoning to PostgreSQL (every cycle, even holds)
6. **Log** — also logs to plan-specific trade history if running via Investment Plans

## Security

- Single-user app (email allowlist: `ALLOWED_EMAIL`)
- Supabase Google OAuth with ES256 JWT verified via JWKS
- Security headers: HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- CORS restricted to production domain
- Rate limiting via slowapi (2/min on `/run`, 60/min global)
- Guardrails validated with Pydantic (prevents config injection)
- Guardrails config stored in PostgreSQL (persists across deploys)
- Prompt injection protection: whitelisted keys sent to Claude
- Kill switch with activate/deactivate endpoints + audit trail
- Race condition protection via asyncio.Lock on trade cycles
- Error responses sanitized (no internal details leaked)

## Deployment

Both services deploy from the same GitHub repo to Railway:

| Service | Root Directory | Port |
|---------|---------------|------|
| bahtzang-frontend | `/frontend` | 3060 |
| bahtzang-backend | `/backend` | 4060 |

Database and auth hosted on Supabase. DNS via Squarespace (CNAME → Railway).
