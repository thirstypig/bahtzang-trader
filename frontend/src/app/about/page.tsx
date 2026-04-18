const TECH_STACK = {
  Frontend: [
    { name: "Next.js 14", desc: "App Router + Server Components" },
    { name: "React 18", desc: "Client-side interactivity" },
    { name: "Tailwind CSS", desc: "Light/dark theme via CSS custom properties" },
    { name: "Recharts", desc: "Portfolio charts and analytics" },
    { name: "Supabase JS", desc: "Auth + session management" },
  ],
  Backend: [
    { name: "Python FastAPI", desc: "Async API framework" },
    { name: "Claude Sonnet", desc: "AI trading decision engine (30s timeout)" },
    { name: "SQLAlchemy 2.0", desc: "Database ORM with Mapped types" },
    { name: "APScheduler", desc: "Configurable 1x/3x/5x daily on market days" },
    { name: "PyJWT + JWKS", desc: "Supabase ES256 token verification" },
  ],
  Infrastructure: [
    { name: "Railway", desc: "Backend + frontend hosting" },
    { name: "Supabase", desc: "PostgreSQL + Google OAuth" },
    { name: "Squarespace", desc: "DNS for bahtzang.com" },
    { name: "GitHub", desc: "Source control + CI/CD trigger" },
  ],
  "Brokers & Data": [
    { name: "Alpaca", desc: "Primary broker — zero-commission stocks, ETFs, options, crypto" },
    { name: "Schwab", desc: "Backup broker — stocks, ETFs, treasuries" },
    { name: "Alpaca Data API", desc: "OHLCV bars, live quotes, technical indicators" },
    { name: "Alpha Vantage", desc: "News sentiment analysis" },
    { name: "Finnhub", desc: "Earnings calendar with position sizing integration" },
  ],
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-primary">About</h1>
        <p className="mt-1 text-sm text-muted">
          How bahtzang.trader is built
        </p>
      </div>

      {/* Architecture */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Architecture</h2>
        <div className="mt-4 overflow-x-auto rounded-lg bg-surface p-6 font-mono text-xs text-secondary">
          <pre>{`
┌─────────────────────────────────────────────────────────────┐
│                    www.bahtzang.com                          │
│               Next.js 14 (Railway) · 22 pages               │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │Dashboard │  │ Trades   │  │  Plans   │  │ Backtest │  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└────────┼──────────────┼──────────────┼──────────────┼───────┘
         │              │              │              │
         └──────────────┴──────┬───────┴──────────────┘
                               │ REST API + Bearer JWT
┌──────────────────────────────┴──────────────────────────────┐
│                   FastAPI Backend (Railway)                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │Claude Brain│  │Guardrails │  │ Scheduler │               │
│  │  (Sonnet) │  │+ Kill SW  │  │ 1x/3x/5x │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │              │              │                       │
│  ┌─────┴──────────────┴──────────────┴─────┐                │
│  │           Trade Executor Pipeline        │                │
│  │  Gather → Think → Validate → Act → Log  │                │
│  └──┬──────────┬──────────┬────────────┬───┘                │
└─────┼──────────┼──────────┼────────────┼────────────────────┘
      │          │          │            │
 ┌────┴────┐ ┌──┴───┐ ┌────┴────┐ ┌─────┴─────┐
 │ Alpaca  │ │Alpha │ │Finnhub  │ │ Supabase  │
 │(primary)│ │Vantage│ │(earnings│ │ PostgreSQL│
 │ Schwab  │ │(news) │ │calendar)│ │ (trades)  │
 │(backup) │ └──────┘ └─────────┘ └───────────┘
 └─────────┘`}</pre>
        </div>
      </div>

      {/* Tech Stack Grid */}
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {Object.entries(TECH_STACK).map(([category, items]) => (
          <div
            key={category}
            className="rounded-xl border border-border bg-card p-6"
          >
            <h3 className="text-sm font-semibold text-accent">
              {category}
            </h3>
            <ul className="mt-3 space-y-2">
              {items.map((item) => (
                <li key={item.name} className="flex items-baseline gap-2">
                  <span className="text-sm font-medium text-primary">
                    {item.name}
                  </span>
                  <span className="text-xs text-muted">— {item.desc}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Design Philosophy */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Design Philosophy</h2>
        <div className="mt-4 space-y-3 text-sm text-secondary">
          <p>
            <strong className="text-primary">AI decides, guardrails enforce.</strong>{" "}
            Claude analyzes portfolio + market data + news and makes trading
            decisions. Every decision passes through guardrails before execution.
            The kill switch overrides everything.
          </p>
          <p>
            <strong className="text-primary">Every decision is logged.</strong>{" "}
            The trades table records every cycle — even holds and blocked trades
            — with full reasoning. This creates a complete audit trail for
            performance analysis and regulatory compliance.
          </p>
          <p>
            <strong className="text-primary">Investment Plans.</strong>{" "}
            Split your portfolio into independent pie-style slices, each with
            its own budget, goal, risk profile, and virtual cash tracking.
            Plans trade independently using fractional shares so every dollar
            of your budget gets put to work.
          </p>
          <p>
            <strong className="text-primary">Defense in depth.</strong>{" "}
            Authentication (Supabase JWT), authorization (email allowlist),
            guardrails (trade limits), circuit breakers (drawdown halts), and
            kill switch (manual override) — five layers of protection.
          </p>
        </div>
      </div>
    </div>
  );
}
