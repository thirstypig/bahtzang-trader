"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4060";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";

interface ServiceCheck {
  name: string;
  url: string;
  status: "operational" | "degraded" | "down" | "checking";
  responseTime: number | null;
  lastChecked: string | null;
}

const STATUS_STYLES = {
  operational: { dot: "bg-emerald-500", text: "text-emerald-400", label: "Operational" },
  degraded: { dot: "bg-amber-500", text: "text-amber-400", label: "Degraded" },
  down: { dot: "bg-red-500", text: "text-red-400", label: "Down" },
  checking: { dot: "bg-zinc-500 animate-pulse", text: "text-zinc-400", label: "Checking..." },
};

// 013-fix: Define service definitions as a constant (not in state)
const SERVICE_DEFS = [
  { name: "Backend API", url: `${API}/health` },
  { name: "Supabase", url: `${SUPABASE_URL}/auth/v1/health` },
  { name: "Frontend", url: "" }, // always operational (we're running)
];

export default function StatusPage() {
  const { user } = useAuth();
  const [services, setServices] = useState<ServiceCheck[]>(
    SERVICE_DEFS.map((s) => ({
      ...s,
      status: s.name === "Frontend" ? "operational" : "checking",
      responseTime: null,
      lastChecked: s.name === "Frontend" ? new Date().toISOString() : null,
    }))
  );

  useEffect(() => {
    if (!user) return;

    async function checkService(url: string) {
      const start = performance.now();
      try {
        const res = await fetch(url, { method: "GET", signal: AbortSignal.timeout(5000) });
        return {
          status: (res.ok ? "operational" : "degraded") as "operational" | "degraded",
          responseTime: Math.round(performance.now() - start),
          lastChecked: new Date().toISOString(),
        };
      } catch {
        return {
          status: "down" as const,
          responseTime: null,
          lastChecked: new Date().toISOString(),
        };
      }
    }

    async function runChecks() {
      // 013-fix: Use functional state update to avoid stale closure
      const results = await Promise.all(
        SERVICE_DEFS.map(async (def) => {
          if (!def.url) {
            return { status: "operational" as const, responseTime: null, lastChecked: new Date().toISOString() };
          }
          return checkService(def.url);
        })
      );

      setServices(
        SERVICE_DEFS.map((def, i) => ({
          ...def,
          ...results[i],
        }))
      );
    }

    runChecks();
    const interval = setInterval(runChecks, 300000);
    return () => clearInterval(interval);
  }, [user]);

  const allOperational = services.every((s) => s.status === "operational");

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">System Status</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Real-time health of all services
        </p>
      </div>

      <div
        className={`rounded-xl border p-4 ${
          allOperational
            ? "border-emerald-900/50 bg-emerald-950/20"
            : "border-amber-900/50 bg-amber-950/20"
        }`}
      >
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              allOperational ? "bg-emerald-500" : "bg-amber-500"
            }`}
          />
          <span className={allOperational ? "text-emerald-400" : "text-amber-400"}>
            {allOperational
              ? "All systems operational"
              : "Some systems may be experiencing issues"}
          </span>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {services.map((service) => {
          const style = STATUS_STYLES[service.status];
          return (
            <div
              key={service.name}
              className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900 px-6 py-4"
            >
              <div className="flex items-center gap-3">
                <div className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
                <span className="text-sm font-medium text-white">{service.name}</span>
              </div>
              <div className="flex items-center gap-4">
                {service.responseTime !== null && (
                  <span className="text-xs text-zinc-500">{service.responseTime}ms</span>
                )}
                <span className={`text-xs font-medium ${style.text}`}>{style.label}</span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-6 text-center text-xs text-zinc-600">Auto-refreshes every 5 minutes</p>
    </div>
  );
}
