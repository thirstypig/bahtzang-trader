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
