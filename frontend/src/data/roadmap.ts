export interface RoadmapItem {
  id: string;
  title: string;
  description: string;
  status: "planned" | "in-progress" | "done";
  priority: "high" | "medium" | "low";
  phase: string;
}

export const roadmapItems: RoadmapItem[] = [
  // Done
  {
    id: "deploy",
    title: "Deploy to Railway + Supabase",
    description: "Backend API, frontend, PostgreSQL, Google OAuth via Supabase",
    status: "done",
    priority: "high",
    phase: "Phase 0",
  },
  {
    id: "auth",
    title: "Google OAuth authentication",
    description: "Supabase Auth with ES256 JWT verification, single-email allowlist",
    status: "done",
    priority: "high",
    phase: "Phase 0",
  },
  {
    id: "dashboard",
    title: "Trading dashboard",
    description: "Portfolio summary, Claude decisions, allocation chart, value chart",
    status: "done",
    priority: "high",
    phase: "Phase 0",
  },
  {
    id: "alpaca",
    title: "Alpaca Markets integration",
    description: "Zero-commission stocks, ETFs, options, crypto — primary broker with async SDK",
    status: "done",
    priority: "high",
    phase: "Phase 1",
  },
  {
    id: "multi-broker",
    title: "Broker abstraction layer",
    description: "BrokerInterface ABC with Alpaca (primary) and Schwab (backup) implementations",
    status: "done",
    priority: "high",
    phase: "Phase 1",
  },
  {
    id: "goals-frequency",
    title: "Trading goals + frequency control",
    description: "6 trading goals with Claude prompts, 1x/3x/5x frequency wired to APScheduler",
    status: "done",
    priority: "high",
    phase: "Phase 1",
  },
  {
    id: "code-review",
    title: "8-agent code review + 24 fixes",
    description: "Guardrails to PostgreSQL, kill switch deactivation, rate limiting, security headers, async Alpaca, Claude timeout",
    status: "done",
    priority: "high",
    phase: "Phase 1",
  },
  {
    id: "notifications",
    title: "Slack trade notifications",
    description: "Fire-and-forget webhooks for trades, blocks, kill switch, daily summary",
    status: "done",
    priority: "high",
    phase: "Phase A",
  },
  {
    id: "portfolio-analytics",
    title: "Portfolio snapshots + equity curve",
    description: "Daily snapshots at 4:05 PM ET, equity curve vs SPY, drawdown chart, Sharpe/Sortino/metrics",
    status: "done",
    priority: "high",
    phase: "Phase B",
  },
  {
    id: "technical-indicators",
    title: "Technical indicators + sector rotation",
    description: "RSI/MACD/BBands/SMA/ATR via pandas-ta, 11 sector ETFs vs SPY, CSV prompt format",
    status: "done",
    priority: "high",
    phase: "Phase C",
  },
  {
    id: "risk-management",
    title: "Risk management subsystem",
    description: "Quarter-Kelly sizing, 3-tier circuit breakers, PDT compliance, wash sale detection",
    status: "done",
    priority: "high",
    phase: "Phase D",
  },
  {
    id: "admin-pages",
    title: "Admin system (13 pages)",
    description: "Todo CRUD API, Concepts tabs, cross-linking, AdminNav, changelog with security badges",
    status: "done",
    priority: "medium",
    phase: "Phase 5",
  },
  // Planned
  {
    id: "backtest",
    title: "Backtesting framework",
    description: "Lightweight simulation engine with pluggable strategies (SMA Crossover, RSI Mean Reversion, Buy & Hold), OHLCV caching, lookahead bias prevention",
    status: "in-progress",
    priority: "high",
    phase: "Phase F",
  },
  {
    id: "paper-to-live",
    title: "Paper-to-live transition",
    description: "Graduated scale-up: 10% → 25% → 50% → 100% of capital over 3 months",
    status: "planned",
    priority: "medium",
    phase: "Phase G",
  },
  {
    id: "earnings-calendar",
    title: "Earnings calendar integration",
    description: "Finnhub API for upcoming earnings, reduces position sizes within 2 days of reporting — 50% at 0-1d, 70% at 2d",
    status: "in-progress",
    priority: "high",
    phase: "Phase F",
  },
];
