import {
  BacktestDetail,
  BacktestItem,
  CycleResult,
  EarningsEvent,
  Guardrails,
  InvestmentPlan,
  PlanMetrics,
  PlanPosition,
  PlanSnapshotData,
  Portfolio,
  StrategyInfo,
  Trade,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4060";

// Token is set by the AuthProvider via setApiToken() whenever the
// Supabase session changes. This avoids calling getSession() which
// can return stale data.
let _accessToken: string | null = null;

export function setApiToken(token: string | null) {
  _accessToken = token;
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  // 012-fix: Merge headers instead of overwriting with spread
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...headers, ...(options?.headers as Record<string, string>) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    // Handle structured error responses (object with error_code + message + ref)
    if (detail && typeof detail === "object" && detail.message) {
      const err: Error & { code?: string; errorType?: string; ref?: string } =
        new Error(detail.message);
      err.code = detail.error_code;
      err.errorType = detail.error_type;
      err.ref = detail.ref;
      throw err;
    }
    throw new Error(typeof detail === "string" ? detail : res.statusText);
  }
  return res.json();
}

export async function getPortfolio(): Promise<Portfolio> {
  return fetchAPI<Portfolio>("/portfolio");
}

export async function getTrades(limit = 50): Promise<Trade[]> {
  return fetchAPI<Trade[]>(`/trades?limit=${limit}`);
}

export async function exportTradesCsv(year?: number): Promise<void> {
  const params = year ? `?year=${year}` : "";
  const headers: Record<string, string> = {};
  if (_accessToken) headers["Authorization"] = `Bearer ${_accessToken}`;
  const res = await fetch(`${API}/trades/export${params}`, { headers });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `bahtzang-trades-${year || "all"}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function getGuardrails(): Promise<Guardrails> {
  return fetchAPI<Guardrails>("/guardrails");
}

export async function updateGuardrails(
  config: Partial<Guardrails>
): Promise<Guardrails> {
  return fetchAPI<Guardrails>("/guardrails", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export interface BotStatus {
  running: boolean;
  frequency: string;
  schedule_times: string[];
  kill_switch: boolean;
  risk_profile: string;
  trading_goal: string;
  last_run: string | null;
  last_action: string | null;
  last_ticker: string | null;
  next_run: string | null;
  total_trades: number;
  recent_changes: {
    action: string;
    timestamp: string;
    changes: string;
  }[];
}

export async function getBotStatus(): Promise<BotStatus> {
  return fetchAPI<BotStatus>("/bot/status");
}

export interface ErrorSummary {
  ref: string;
  error_code: string;
  message: string;
  path: string;
  method: string;
  timestamp: string;
}

export interface ErrorDetail extends ErrorSummary {
  error_type: string;
  stack: string;
  user_email: string;
}

export async function getRecentErrors(limit = 20): Promise<{ total: number; errors: ErrorSummary[] }> {
  return fetchAPI<{ total: number; errors: ErrorSummary[] }>(`/admin/errors?limit=${limit}`);
}

export async function getErrorByRef(ref: string): Promise<ErrorDetail> {
  return fetchAPI<ErrorDetail>(`/admin/errors/${ref}`);
}

export async function activateKillSwitch(): Promise<{ status: string }> {
  return fetchAPI<{ status: string }>("/killswitch", { method: "POST" });
}

export async function deactivateKillSwitch(): Promise<{ status: string }> {
  return fetchAPI<{ status: string }>("/killswitch/deactivate", { method: "POST" });
}

export async function triggerRun(): Promise<CycleResult> {
  return fetchAPI<CycleResult>("/run", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Portfolio Analytics
// ---------------------------------------------------------------------------

export interface SnapshotData {
  date: string;
  total_equity: number;
  cash: number;
  invested: number;
  unrealized_pnl: number;
  spy_close: number | null;
  deposit_withdrawal: number;
}

export interface PortfolioMetrics {
  total_return_pct: number;
  sharpe_ratio: number | null;
  sharpe_confidence: string;
  sortino_ratio: number | null;
  max_drawdown_pct: number;
  max_drawdown_days: number;
  win_rate_pct: number;
  profit_factor: number | null;
  best_day_pct: number;
  worst_day_pct: number;
  volatility_annual_pct: number;
  num_trading_days: number;
}

export async function getSnapshots(days = 90): Promise<SnapshotData[]> {
  return fetchAPI<SnapshotData[]>(`/portfolio/snapshots?days=${days}`);
}

export async function getPortfolioMetrics(days = 90): Promise<PortfolioMetrics> {
  return fetchAPI<PortfolioMetrics>(`/portfolio/metrics?days=${days}`);
}

export async function takeSnapshot(): Promise<{ status: string }> {
  return fetchAPI<{ status: string }>("/portfolio/snapshot", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Admin Todos
// ---------------------------------------------------------------------------

export interface TodoTask {
  id: string;
  title: string;
  category: string;
  status: "not_started" | "in_progress" | "done";
  priority: "p0" | "p1" | "p2" | "p3";
  owner: string | null;
  description: string | null;
  steps: string[] | null;
  roadmap_link: string | null;
  concept_link: string | null;
  target_date: string | null;
  created_at: string;
  updated_at: string;
}

export async function getTodos(): Promise<TodoTask[]> {
  return fetchAPI<TodoTask[]>("/admin/todos");
}

export async function createTodo(
  task: Partial<TodoTask>
): Promise<TodoTask> {
  return fetchAPI<TodoTask>("/admin/todos", {
    method: "POST",
    body: JSON.stringify(task),
  });
}

export async function updateTodo(
  id: string,
  updates: Partial<TodoTask>
): Promise<TodoTask> {
  return fetchAPI<TodoTask>(`/admin/todos/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function deleteTodo(id: string): Promise<void> {
  await fetchAPI<void>(`/admin/todos/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------

export async function getStrategies(): Promise<StrategyInfo[]> {
  return fetchAPI<StrategyInfo[]>("/backtest/strategies");
}

export async function createBacktest(config: {
  name: string;
  strategy: string;
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  params: Record<string, unknown>;
  max_position_pct: number;
  max_positions: number;
  stop_loss_pct: number;
}): Promise<{ config_id: number; result_id: number; status: string }> {
  return fetchAPI("/backtest", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function listBacktests(): Promise<BacktestItem[]> {
  return fetchAPI<BacktestItem[]>("/backtest");
}

export async function getBacktestResult(
  resultId: number
): Promise<BacktestDetail> {
  return fetchAPI<BacktestDetail>(`/backtest/${resultId}`);
}

export async function deleteBacktest(configId: number): Promise<void> {
  await fetchAPI(`/backtest/${configId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Earnings Calendar
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

export async function getPlans(): Promise<InvestmentPlan[]> {
  return fetchAPI<InvestmentPlan[]>("/plans");
}

export async function getPlan(id: number): Promise<InvestmentPlan & { trades: Trade[] }> {
  return fetchAPI<InvestmentPlan & { trades: Trade[] }>(`/plans/${id}`);
}

export async function createPlan(plan: {
  name: string;
  budget: number;
  trading_goal: string;
  risk_profile?: string;
  trading_frequency?: string;
  target_amount?: number | null;
  target_date?: string | null;
}): Promise<InvestmentPlan> {
  return fetchAPI<InvestmentPlan>("/plans", {
    method: "POST",
    body: JSON.stringify(plan),
  });
}

export async function updatePlan(
  id: number,
  updates: Partial<InvestmentPlan>,
): Promise<InvestmentPlan> {
  return fetchAPI<InvestmentPlan>(`/plans/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function deletePlan(id: number): Promise<void> {
  await fetchAPI(`/plans/${id}`, { method: "DELETE" });
}

export async function runPlan(id: number): Promise<CycleResult> {
  return fetchAPI<CycleResult>(`/plans/${id}/run`, { method: "POST" });
}

export async function exportPlanTradesCsv(id: number): Promise<void> {
  const headers: Record<string, string> = {};
  if (_accessToken) headers["Authorization"] = `Bearer ${_accessToken}`;
  const res = await fetch(`${API}/plans/${id}/export`, { headers });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `bahtzang-plan-${id}-trades.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function getPlanPositions(id: number): Promise<PlanPosition[]> {
  return fetchAPI<PlanPosition[]>(`/plans/${id}/positions`);
}

export async function getPlanSnapshots(
  id: number,
  days = 90,
): Promise<PlanSnapshotData[]> {
  return fetchAPI<PlanSnapshotData[]>(`/plans/${id}/snapshots?days=${days}`);
}

export async function getPlanMetrics(
  id: number,
  days = 90,
): Promise<PlanMetrics> {
  return fetchAPI<PlanMetrics>(`/plans/${id}/metrics?days=${days}`);
}

export async function getEarningsCalendar(
  days = 30
): Promise<{ earnings: EarningsEvent[]; count: number }> {
  return fetchAPI<{ earnings: EarningsEvent[]; count: number }>(
    `/earnings?days=${days}`
  );
}

export async function refreshEarnings(): Promise<{
  status: string;
  events_cached: number;
}> {
  return fetchAPI<{ status: string; events_cached: number }>(
    "/earnings/refresh",
    { method: "POST" }
  );
}
