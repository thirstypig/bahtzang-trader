export interface ChangelogEntry {
  version: string;
  date: string;
  changes: {
    type: "feat" | "fix" | "docs" | "perf" | "refactor" | "security";
    title: string;
  }[];
  roadmapLink?: string;
}

export const changelog: ChangelogEntry[] = [
  {
    version: "0.11.0",
    date: "2026-04-13",
    roadmapLink: "/roadmap#risk-management",
    changes: [
      { type: "feat", title: "Quarter-Kelly position sizing with confidence^2 modifier" },
      { type: "feat", title: "3-tier circuit breakers (YELLOW/ORANGE/RED) based on portfolio P&L" },
      { type: "feat", title: "PDT day trade compliance tracking (accounts <$25k)" },
      { type: "feat", title: "Wash sale 30-day cooling period detection" },
      { type: "feat", title: "5 new guardrails config fields for risk management" },
    ],
  },
  {
    version: "0.10.0",
    date: "2026-04-13",
    roadmapLink: "/roadmap#technical-indicators",
    changes: [
      { type: "feat", title: "Technical indicators via pandas-ta (RSI, MACD, BBands, SMA, ATR)" },
      { type: "feat", title: "Alpaca Data API replaces Alpha Vantage for OHLCV (200 req/min)" },
      { type: "feat", title: "Sector rotation signals for 11 ETFs vs SPY (LEADING/LAGGING)" },
      { type: "perf", title: "CSV prompt format — 56% fewer tokens than JSON" },
      { type: "feat", title: "Daily indicator caching (recompute once per trading day)" },
    ],
  },
  {
    version: "0.9.0",
    date: "2026-04-13",
    roadmapLink: "/roadmap#portfolio-analytics",
    changes: [
      { type: "feat", title: "Daily portfolio snapshots at 4:05 PM ET (Alpaca + SPY benchmark)" },
      { type: "feat", title: "Analytics engine: Sharpe, Sortino, max drawdown, win rate, profit factor" },
      { type: "feat", title: "Equity curve chart — portfolio vs SPY normalized returns" },
      { type: "feat", title: "Drawdown chart with red gradient fill" },
      { type: "feat", title: "Return distribution histogram" },
      { type: "feat", title: "Manual 'Take Snapshot Now' button + API endpoint" },
      { type: "feat", title: "Sharpe confidence indicator (low/moderate/high based on data quantity)" },
    ],
  },
  {
    version: "0.8.0",
    date: "2026-04-12",
    changes: [
      { type: "feat", title: "Admin system: interconnected Todo + Concepts pages with cross-links" },
      { type: "feat", title: "API-backed todo CRUD with JSON file persistence" },
      { type: "feat", title: "Concepts page with URL-based tabs (Strategic/SEO/Integrations/UX)" },
      { type: "feat", title: "CrossLink badge component + AdminNav shared navigation" },
      { type: "feat", title: "Smooth scroll anchoring with fixed navbar offset" },
    ],
  },
  {
    version: "0.7.0",
    date: "2026-04-12",
    roadmapLink: "/roadmap#code-review",
    changes: [
      { type: "security", title: "Migrate guardrails from JSON file to PostgreSQL" },
      { type: "feat", title: "Add kill switch deactivation endpoint + Resume Trading UI" },
      { type: "feat", title: "Wire trading frequency to APScheduler (1x/3x/5x per day)" },
      { type: "fix", title: "Fix max_positions counting all-time buys instead of current positions" },
      { type: "feat", title: "Add Slack trade notifications (fire-and-forget)" },
      { type: "security", title: "Add rate limiting, security headers, error response sanitization" },
      { type: "feat", title: "Add guardrails audit trail with user + timestamp" },
      { type: "perf", title: "Wrap Alpaca SDK in asyncio.to_thread() — non-blocking event loop" },
      { type: "perf", title: "Add 30s timeout on Claude API call with graceful hold fallback" },
      { type: "security", title: "Whitelist guardrail keys sent to Claude (prompt injection protection)" },
    ],
  },
  {
    version: "0.6.0",
    date: "2026-04-10",
    changes: [
      { type: "refactor", title: "Feature module isolation: routes/ and brokers/ directories" },
      { type: "refactor", title: "BrokerInterface abstraction — swap brokers by changing one line" },
      { type: "refactor", title: "main.py split into 4 route modules (65 lines vs 136)" },
      { type: "docs", title: "README rewritten with architecture diagram, all pages, deployment guide" },
      { type: "docs", title: "CLAUDE.md updated with new module structure" },
    ],
  },
  {
    version: "0.5.0",
    date: "2026-04-10",
    changes: [
      { type: "fix", title: "P1: AsyncAnthropic — event loop no longer freezes during Claude calls" },
      { type: "fix", title: "P1: Guardrails input validation — Pydantic model prevents config bypass" },
      { type: "fix", title: "P1: Schwab token cache with expiry — auto-refreshes after 30min" },
      { type: "fix", title: "P1: CORS restricted to GET/POST + specific headers" },
      { type: "perf", title: "P2: Parallel API calls — pipeline 5.7s → 3.7s (35% faster)" },
      { type: "perf", title: "P2: Shared httpx clients — no more per-request TCP/TLS overhead" },
      { type: "fix", title: "P2: asyncio.Lock prevents concurrent guardrail bypass" },
      { type: "fix", title: "P2: fetchAPI headers merge — auth token no longer silently dropped" },
      { type: "fix", title: "P2: Status page stale closure bug fixed" },
      { type: "fix", title: "P2: Portfolio returns 503 instead of fake $0 on errors" },
      { type: "fix", title: "P2: datetime.utcnow → timezone-aware datetime.now(UTC)" },
      { type: "refactor", title: "P3: Extracted Spinner component (6 copies → 1)" },
      { type: "refactor", title: "P3: Removed dead code, empty dirs, duplicate nav link" },
      { type: "perf", title: "P3: Static pages now Server Components (smaller JS bundles)" },
      { type: "fix", title: "P3: 'Win Rate' renamed to 'High Confidence Rate' (honest metric)" },
      { type: "perf", title: "P3: Database indexes on trades table" },
    ],
  },
  {
    version: "0.4.0",
    date: "2026-04-10",
    changes: [
      { type: "feat", title: "Admin pages: roadmap, changelog, about, status, docs, audit log" },
      { type: "feat", title: "To-do list page with step-by-step instructions and filters" },
      { type: "feat", title: "Analytics page with performance metrics" },
      { type: "feat", title: "Updated navigation with grouped 'More' dropdown" },
      { type: "feat", title: "HSTS header for forced HTTPS" },
      { type: "docs", title: "CLAUDE.md project conventions file" },
      { type: "docs", title: "Deepened roadmap plan with 8-agent research synthesis" },
    ],
  },
  {
    version: "0.3.0",
    date: "2026-04-09",
    changes: [
      { type: "feat", title: "Migrate auth and database to Supabase" },
      { type: "fix", title: "JWT verification: ES256 via JWKS endpoint (not legacy HS256)" },
      { type: "fix", title: "Token injection from AuthProvider to API layer" },
      { type: "fix", title: "Graceful error handling when Schwab API unavailable" },
      { type: "feat", title: "Two-service Railway deployment (frontend + backend)" },
      { type: "feat", title: "Custom domain: www.bahtzang.com via Squarespace DNS" },
    ],
  },
  {
    version: "0.2.0",
    date: "2026-04-08",
    changes: [
      { type: "feat", title: "Google OAuth authentication with JWT sessions" },
      { type: "feat", title: "Login page with Google Sign-In" },
      { type: "feat", title: "Navbar with profile photo and sign-out" },
      { type: "feat", title: "Route protection — redirect to /login when unauthenticated" },
    ],
  },
  {
    version: "0.1.0",
    date: "2026-04-08",
    changes: [
      { type: "feat", title: "Next.js 14 dashboard with dark theme and Recharts" },
      { type: "feat", title: "FastAPI backend with Claude AI decision engine" },
      { type: "feat", title: "Schwab API client for portfolio and order management" },
      { type: "feat", title: "Alpha Vantage market data and news integration" },
      { type: "feat", title: "Guardrails system with kill switch" },
      { type: "feat", title: "APScheduler cron at 9:35 AM ET on market days" },
      { type: "feat", title: "Railway deployment configuration" },
    ],
  },
];
