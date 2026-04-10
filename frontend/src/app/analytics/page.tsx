"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getTrades } from "@/lib/api";
import { Trade } from "@/lib/types";

export default function AnalyticsPage() {
  const { user } = useAuth();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    getTrades(500)
      .then(setTrades)
      .catch(() => setTrades([]))
      .finally(() => setLoading(false));
  }, [user]);

  const executed = trades.filter((t) => t.executed && t.action !== "hold");
  const wins = executed.filter((t) => t.confidence && t.confidence > 0.6);
  const winRate = executed.length > 0 ? wins.length / executed.length : 0;
  const avgConfidence =
    trades.length > 0
      ? trades.reduce((s, t) => s + (t.confidence || 0), 0) / trades.length
      : 0;
  const blocked = trades.filter((t) => !t.guardrail_passed);

  const metrics = [
    {
      label: "Total Decisions",
      value: trades.length.toString(),
      sub: "All bot cycles recorded",
      color: "text-white",
    },
    {
      label: "Executed Trades",
      value: executed.length.toString(),
      sub: `${blocked.length} blocked by guardrails`,
      color: "text-emerald-400",
    },
    {
      label: "Win Rate",
      value: `${(winRate * 100).toFixed(1)}%`,
      sub: "Trades with confidence > 60%",
      color: winRate >= 0.55 ? "text-emerald-400" : "text-amber-400",
    },
    {
      label: "Avg Confidence",
      value: `${(avgConfidence * 100).toFixed(1)}%`,
      sub: "Claude's average conviction",
      color: "text-blue-400",
    },
  ];

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Trading performance metrics and analysis
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="rounded-xl border border-zinc-800 bg-zinc-900 p-6"
          >
            <p className="text-xs text-zinc-500">{m.label}</p>
            <p className={`mt-2 text-3xl font-bold ${m.color}`}>{m.value}</p>
            <p className="mt-1 text-xs text-zinc-600">{m.sub}</p>
          </div>
        ))}
      </div>

      {/* Placeholder for future charts */}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="flex h-64 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
          <div className="text-center">
            <p className="text-sm text-zinc-500">Equity Curve vs S&P 500</p>
            <p className="mt-1 text-xs text-zinc-600">
              Coming in Phase 4 — requires daily portfolio snapshots
            </p>
          </div>
        </div>
        <div className="flex h-64 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
          <div className="text-center">
            <p className="text-sm text-zinc-500">Drawdown Chart</p>
            <p className="mt-1 text-xs text-zinc-600">
              Coming in Phase 4 — requires historical balance data
            </p>
          </div>
        </div>
        <div className="flex h-64 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
          <div className="text-center">
            <p className="text-sm text-zinc-500">
              Sharpe Ratio &amp; Risk Metrics
            </p>
            <p className="mt-1 text-xs text-zinc-600">
              Coming in Phase 4 — requires daily returns calculation
            </p>
          </div>
        </div>
        <div className="flex h-64 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
          <div className="text-center">
            <p className="text-sm text-zinc-500">Confidence Calibration</p>
            <p className="mt-1 text-xs text-zinc-600">
              Coming in Phase 4 — tracks Claude accuracy vs confidence
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
