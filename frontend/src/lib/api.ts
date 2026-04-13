import { CycleResult, Guardrails, Portfolio, Trade } from "./types";

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
      const err = new Error(detail.message);
      (err as any).code = detail.error_code;
      (err as any).errorType = detail.error_type;
      (err as any).ref = detail.ref;
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
