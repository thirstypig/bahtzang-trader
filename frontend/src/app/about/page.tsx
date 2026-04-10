const TECH_STACK = {
  Frontend: [
    { name: "Next.js 14", desc: "App Router + Server Components" },
    { name: "React 18", desc: "Client-side interactivity" },
    { name: "Tailwind CSS", desc: "Dark-themed utility-first styling" },
    { name: "Recharts", desc: "Portfolio charts and analytics" },
    { name: "Supabase JS", desc: "Auth + session management" },
  ],
  Backend: [
    { name: "Python FastAPI", desc: "Async API framework" },
    { name: "Claude Sonnet", desc: "AI trading decision engine" },
    { name: "SQLAlchemy 2.0", desc: "Database ORM with Mapped types" },
    { name: "APScheduler", desc: "9:35 AM ET cron on market days" },
    { name: "PyJWT + JWKS", desc: "Supabase ES256 token verification" },
  ],
  Infrastructure: [
    { name: "Railway", desc: "Backend + frontend hosting" },
    { name: "Supabase", desc: "PostgreSQL + Google OAuth" },
    { name: "Squarespace", desc: "DNS for bahtzang.com" },
    { name: "GitHub", desc: "Source control + CI/CD trigger" },
  ],
  "Data Sources": [
    { name: "Schwab API", desc: "Portfolio positions + order execution" },
    { name: "Alpha Vantage", desc: "Live quotes + news sentiment" },
    { name: "Alpaca (planned)", desc: "Zero-commission multi-asset trading" },
    { name: "Finnhub (planned)", desc: "Earnings calendar integration" },
  ],
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">About</h1>
        <p className="mt-1 text-sm text-zinc-500">
          How bahtzang.trader is built
        </p>
      </div>

      {/* Architecture */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Architecture</h2>
        <div className="mt-4 overflow-x-auto rounded-lg bg-zinc-950 p-6 font-mono text-xs text-zinc-400">
          <pre>{`
┌─────────────────────────────────────────────────────────────┐
│                    www.bahtzang.com                          │
│                  Next.js 14 (Railway)                        │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │Dashboard │  │ Trades   │  │ Settings │  │  Admin   │  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└────────┼──────────────┼──────────────┼──────────────┼───────┘
         │              │              │              │
         └──────────────┴──────┬───────┴──────────────┘
                               │ REST API + Bearer JWT
┌──────────────────────────────┴──────────────────────────────┐
│                   FastAPI Backend (Railway)                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │Claude Brain│  │Guardrails │  │ Scheduler │               │
│  │  (Sonnet) │  │+ Kill SW  │  │ 9:35 AM ET│               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │              │              │                       │
│  ┌─────┴──────────────┴──────────────┴─────┐                │
│  │           Trade Executor Pipeline        │                │
│  │  Gather → Think → Validate → Act → Log  │                │
│  └─────┬──────────┬──────────────────┬─────┘                │
└────────┼──────────┼──────────────────┼──────────────────────┘
         │          │                  │
    ┌────┴────┐ ┌───┴────┐      ┌─────┴─────┐
    │Schwab/  │ │Alpha   │      │ Supabase  │
    │Alpaca   │ │Vantage │      │ PostgreSQL│
    │(orders) │ │(quotes)│      │ (trades)  │
    └─────────┘ └────────┘      └───────────┘`}</pre>
        </div>
      </div>

      {/* Tech Stack Grid */}
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {Object.entries(TECH_STACK).map(([category, items]) => (
          <div
            key={category}
            className="rounded-xl border border-zinc-800 bg-zinc-900 p-6"
          >
            <h3 className="text-sm font-semibold text-emerald-400">
              {category}
            </h3>
            <ul className="mt-3 space-y-2">
              {items.map((item) => (
                <li key={item.name} className="flex items-baseline gap-2">
                  <span className="text-sm font-medium text-white">
                    {item.name}
                  </span>
                  <span className="text-xs text-zinc-500">— {item.desc}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Design Philosophy */}
      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Design Philosophy</h2>
        <div className="mt-4 space-y-3 text-sm text-zinc-400">
          <p>
            <strong className="text-zinc-200">AI decides, guardrails enforce.</strong>{" "}
            Claude analyzes portfolio + market data + news and makes trading
            decisions. Every decision passes through guardrails before execution.
            The kill switch overrides everything.
          </p>
          <p>
            <strong className="text-zinc-200">Every decision is logged.</strong>{" "}
            The trades table records every cycle — even holds and blocked trades
            — with full reasoning. This creates a complete audit trail for
            performance analysis and regulatory compliance.
          </p>
          <p>
            <strong className="text-zinc-200">Defense in depth.</strong>{" "}
            Authentication (Supabase JWT), authorization (email allowlist),
            guardrails (trade limits), circuit breakers (drawdown halts), and
            kill switch (manual override) — five layers of protection.
          </p>
        </div>
      </div>
    </div>
  );
}
