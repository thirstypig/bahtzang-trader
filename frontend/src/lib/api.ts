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
    const detail = body.detail || res.statusText;
    throw new Error(detail);
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
