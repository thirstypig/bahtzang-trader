# bahtzang-trader

AI-powered trading bot that uses Claude Sonnet to make buy/sell/hold decisions. Dark-themed Next.js dashboard with real-time portfolio tracking, trade history, and guardrail controls.

**Live at:** [www.bahtzang.com](https://www.bahtzang.com)

## Architecture

```
┌─────────────────────────────────┐
│  Next.js 14 Frontend (Railway)  │  www.bahtzang.com
│  Dashboard · Trades · Settings  │  12 pages + login
│  + 9 admin pages                │
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
│       ├── app/             # 13 pages (dashboard, trades, settings, concepts, etc.)
│       ├── components/      # Reusable UI (Navbar, AdminNav, CrossLink, charts)
│       ├── lib/             # API client, auth, Supabase, types, useHashScroll
│       └── data/            # Static data (roadmap, changelog, concepts)
├── backend/                 # Python FastAPI
│   └── app/
│       ├── main.py          # App setup + router registration + rate limiting
│       ├── routes/          # API route modules (portfolio, trades, guardrails, bot, todos)
│       ├── brokers/         # Broker abstraction (base.py + alpaca.py + schwab.py)
│       ├── auth.py          # Supabase JWT verification via JWKS
│       ├── claude_brain.py  # AI decision engine (AsyncAnthropic, 30s timeout)
│       ├── guardrails.py    # Safety limits + kill switch (stored in PostgreSQL)
│       ├── notifier.py      # Slack webhook notifications (fire-and-forget)
│       ├── trade_executor.py # Pipeline: gather → think → validate → act → log → notify
│       ├── market_data.py   # Alpha Vantage quotes + news
│       └── scheduler.py     # Dynamic frequency (1x/3x/5x) + daily summary
│   └── data/
│       └── todo-tasks.json  # Admin todo tasks (runtime, file-based)
├── docs/plans/              # Architecture roadmap + feature plans
├── todos/                   # Code review findings (44 items, all resolved)
├── CLAUDE.md                # Project conventions for Claude Code
└── package.json             # Root scripts (npm run dev)
```

## Pages

| Page | Description |
|------|------------|
| `/` | Dashboard — portfolio summary, Claude's decisions, charts |
| `/trades` | Trade history with sortable columns |
| `/settings` | Guardrails, kill switch, manual bot trigger |
| `/analytics` | Performance metrics (confidence rate, trade counts) |
| `/roadmap` | Kanban board — planned / in-progress / done, cross-link anchors |
| `/concepts` | Future ideas — tabbed (Strategic / SEO / Integrations / UX) |
| `/changelog` | Version history with feat/fix/security badges, cross-links |
| `/about` | Architecture diagram and tech stack |
| `/status` | Live service health checks |
| `/docs` | Documentation links (GitHub, Swagger, Supabase) |
| `/todos` | API-backed task tracker — categories, progress bars, CRUD |
| `/audit-log` | Expandable trade decision trail |
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

1. **Gather** — fetch portfolio + balances from Alpaca (async, non-blocking)
2. **Think** — send context to Claude Sonnet, get buy/sell/hold decision (30s timeout)
3. **Validate** — run decision through guardrails (kill switch, limits, daily cap, position count)
4. **Act** — execute order on broker if approved
5. **Log** — write decision + reasoning to PostgreSQL (every cycle, even holds)

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
