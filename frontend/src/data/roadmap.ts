export interface RoadmapItem {
  id: string;
  title: string;
  description: string;
  status: "planned" | "in-progress" | "done";
  priority: "high" | "medium" | "low";
  phase: string;
}

export const roadmapItems: RoadmapItem[] = [
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
    description: "Zero-commission stocks, ETFs, options, crypto via Alpaca API",
    status: "planned",
    priority: "high",
    phase: "Phase 1",
  },
  {
    id: "multi-broker",
    title: "Multi-broker router",
    description: "Broker abstraction layer routing trades by asset class",
    status: "planned",
    priority: "high",
    phase: "Phase 1",
  },
  {
    id: "paper-trading",
    title: "Paper trading mode",
    description: "Simulated trading with slippage, side-by-side performance vs live",
    status: "planned",
    priority: "high",
    phase: "Phase 1",
  },
  {
    id: "risk-mgmt",
    title: "Risk management subsystem",
    description: "VaR, Kelly criterion sizing, circuit breakers, PDT compliance",
    status: "planned",
    priority: "high",
    phase: "Phase 3",
  },
  {
    id: "claude-brain",
    title: "Enhanced Claude brain",
    description: "Two-tier screening, technical indicators, sector rotation, earnings calendar",
    status: "planned",
    priority: "high",
    phase: "Phase 2",
  },
  {
    id: "analytics",
    title: "Portfolio analytics",
    description: "Sharpe ratio, drawdown chart, equity curve vs S&P 500, win rate",
    status: "in-progress",
    priority: "medium",
    phase: "Phase 4",
  },
  {
    id: "admin-pages",
    title: "Admin & documentation pages",
    description: "Roadmap, changelog, about, status, docs, audit log",
    status: "in-progress",
    priority: "medium",
    phase: "Phase 5",
  },
  {
    id: "backtest",
    title: "Backtesting framework",
    description: "Historical strategy validation with Backtrader, confidence calibration",
    status: "planned",
    priority: "low",
    phase: "Phase 6",
  },
  {
    id: "alerts",
    title: "Alert & notification system",
    description: "Price alerts, drawdown thresholds, VIX spikes, push notifications",
    status: "planned",
    priority: "medium",
    phase: "Phase 5",
  },
];
