import { CycleResult, Guardrails, Portfolio, Trade } from "./types";
import { getSupabase } from "./supabase";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getToken(): Promise<string | null> {
  const { data } = await getSupabase().auth.getSession();
  return data.session?.access_token || null;
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API}${path}`, { headers, ...options });
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
