import { CycleResult, Guardrails, Portfolio, Trade } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
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
  return fetchAPI("/killswitch", { method: "POST" });
}

export async function triggerRun(): Promise<CycleResult> {
  return fetchAPI<CycleResult>("/run", { method: "POST" });
}
