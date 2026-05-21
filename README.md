# bahtzang-trader

AI-powered trading bot that uses Claude Sonnet to make buy/sell/hold decisions. Next.js dashboard (light/dark theme) with portfolio tracking, trade history, backtesting, earnings calendar, and guardrail controls.

**Live at:** [www.bahtzang.com](https://www.bahtzang.com)

## Architecture

```
┌─────────────────────────────────┐
│  Next.js 14 Frontend (Railway)  │  www.bahtzang.com
│  Portfolio · Trades · Analytics  │  25 pages
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
│       ├── app/             # 25 pages (portfolio, trades, strategies, screener, analytics, backtest, forex, etc.)
│       ├── components/      # Reusable UI (TopNav, ThemeToggle, charts, KillSwitchButton, etc.)
│       ├── lib/             # API client, auth, theme, Supabase, types
│       └── data/            # Static data (roadmap, changelog, concepts)
├── backend/                 # Python FastAPI
│   └── app/
│       ├── main.py          # App setup + router registration + rate limiting
│       ├── routes/          # API route modules (portfolio, trades, guardrails, bot, todos)
│       ├── brokers/         # Broker abstraction (base.py + alpaca.py + schwab.py)
│       ├── auth.py          # Supabase JWT verification via JWKS
│       ├── backtest/         # Backtesting framework (3 strategies, OHLCV cache)
│       ├── earnings/         # Earnings calendar (Finnhub API cache, position sizing)
│       ├── claude_brain.py  # AI decision engine (AsyncAnthropic, 30s timeout)
│       ├── guardrails.py    # Safety limits + kill switch + stop-loss (stored in PostgreSQL)
│       ├── pipeline_types.py # TypedDict definitions (Position, Quote, TradeDecision, etc.)
│       ├── notifier.py      # Slack webhook notifications (fire-and-forget)
│       ├── trade_executor.py # Pipeline: gather → think → validate → act → log → notify
│       ├── market_data.py   # Alpha Vantage news sentiment
│       └── scheduler.py     # Dynamic frequency (1x/3x/5x) + snapshots + earnings refresh
│   └── data/
│       └── todo-tasks.json  # Admin todo tasks (runtime, file-based)
├── docs/plans/              # Architecture roadmap + feature plans
├── todos/                   # Code review findings (100 items, most resolved)
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
| `/backtest` | Backtest strategies (SMA Crossover, RSI Mean Reversion, Buy & Hold) |
| `/earnings` | Upcoming earnings calendar with position sizing integration |
| `/audit-log` | Guardrails config change audit trail |
| `/todos` | API-backed task tracker — categories, progress bars, CRUD |
| `/roadmap` | Kanban board — planned / in-progress / done |
| `/changelog` | Version history with feat/fix/security badges |
| `/errors` | Error log with ERR-XXXXXX reference codes |
| `/status` | Live service health checks |
| `/about` | Architecture diagram, tech stack, design philosophy |
| `/docs` | Documentation links (GitHub, Swagger, Supabase, Railway) |
| `/` | Portfolio — account holdings (shares, cost basis vs market value, P&L) + latest AI decision |
| `/portfolios` | Strategies — sub-accounts with independent budgets, rules, and kill switches |
| `/portfolios/[id]` | Strategy detail — virtual positions, equity curve, trade history, run/export |
| `/screener` | Daily ranked S&P 500 candidates (momentum/trend/relative-strength) — advisory |
| `/forex` | Independent swing-zone strategy backtester (separate from Claude trader) |
| `/testing` | Test inventory, execution cadence, 477 tests (348 backend + 129 frontend) |
| `/concepts` | Feature concepts — tabbed: Strategic/SEO/Integrations/UX |
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
- Production Swagger is disabled for security (096-fix)

## Testing

477 tests (348 backend + 129 frontend), all passing in ~9s. Pre-commit hook + GitHub Actions CI runs `next lint` too.

```bash
npm test                   # Run all tests (backend + frontend)
npm run test:backend       # pytest (348 tests, ~4s)
npm run test:frontend      # Vitest + Testing Library (129 tests, ~3s)
npm run test:backend:cov   # Backend with coverage report
```

## Trading Pipeline

Every cycle (configurable 1x/3x/5x per day, or manual trigger):

1. **Gather** — fetch portfolio + balances from Alpaca, technical indicators (RSI/MACD/BBands/SMA/ATR), sector rotation signals, earnings calendar
2. **Think** — send context to Claude Sonnet, get buy/sell/hold decision (30s timeout)
3. **Validate** — run decision through guardrails (kill switch, stop-loss, limits, daily cap, position count, PDT compliance)
4. **Act** — execute order on Alpaca if approved, with earnings-aware position sizing
5. **Log** — write decision + reasoning to PostgreSQL (every cycle, even holds)
6. **Notify** — Slack webhook notification (fire-and-forget)

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
