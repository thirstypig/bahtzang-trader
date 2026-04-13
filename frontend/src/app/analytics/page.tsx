"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  getTrades,
  getSnapshots,
  getPortfolioMetrics,
  takeSnapshot,
  SnapshotData,
  PortfolioMetrics,
} from "@/lib/api";
import { Trade } from "@/lib/types";
import Spinner from "@/components/Spinner";
import EquityCurveChart from "@/components/EquityCurveChart";
import ReturnDistributionChart from "@/components/ReturnDistributionChart";
import DrawdownChart from "@/components/DrawdownChart";

export default function AnalyticsPage() {
  const { user } = useAuth();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotData[]>([]);
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [snapshotting, setSnapshotting] = useState(false);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      getTrades(500).catch(() => []),
      getSnapshots(90).catch(() => []),
      getPortfolioMetrics(90).catch(() => null),
    ])
      .then(([t, s, m]) => {
        setTrades(t);
        setSnapshots(s);
        if (m && !("error" in m)) setMetrics(m);
      })
      .finally(() => setLoading(false));
  }, [user]);

  async function handleTakeSnapshot() {
    setSnapshotting(true);
    try {
      await takeSnapshot();
      const [s, m] = await Promise.all([
        getSnapshots(90).catch(() => []),
        getPortfolioMetrics(90).catch(() => null),
      ]);
      setSnapshots(s);
      if (m && !("error" in m)) setMetrics(m);
    } finally {
      setSnapshotting(false);
    }
  }

  // Trade-based metrics (always available)
  const executed = trades.filter((t) => t.executed && t.action !== "hold");
  const blocked = trades.filter((t) => !t.guardrail_passed);
  const avgConfidence =
    trades.length > 0
      ? trades.reduce((s, t) => s + (t.confidence || 0), 0) / trades.length
      : 0;

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Performance metrics and portfolio analysis
            {snapshots.length > 0 && ` — ${snapshots.length} daily snapshots`}
          </p>
        </div>
        <button
          onClick={handleTakeSnapshot}
          disabled={snapshotting}
          className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 disabled:opacity-50"
        >
          {snapshotting ? "Capturing..." : "Take Snapshot Now"}
        </button>
      </div>

      {/* Trade Metrics (always available) */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total Decisions"
          value={trades.length.toString()}
          sub="All bot cycles"
          color="text-white"
        />
        <MetricCard
          label="Executed Trades"
          value={executed.length.toString()}
          sub={`${blocked.length} blocked by guardrails`}
          color="text-emerald-400"
        />
        <MetricCard
          label="Avg Confidence"
          value={`${(avgConfidence * 100).toFixed(1)}%`}
          sub="Claude's average conviction"
          color="text-blue-400"
        />
        <MetricCard
          label="Snapshots"
          value={snapshots.length.toString()}
          sub={snapshots.length >= 60 ? "Sharpe is significant" : `${snapshots.length}/60 for Sharpe significance`}
          color={snapshots.length >= 60 ? "text-emerald-400" : "text-amber-400"}
        />
      </div>

      {/* Portfolio Metrics (from snapshots) */}
      {metrics && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Total Return"
            value={`${metrics.total_return_pct >= 0 ? "+" : ""}${metrics.total_return_pct}%`}
            sub={`Over ${metrics.num_trading_days} trading days`}
            color={metrics.total_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}
          />
          <MetricCard
            label={`Sharpe Ratio${metrics.sharpe_confidence !== "high" ? ` (${metrics.sharpe_confidence})` : ""}`}
            value={metrics.sharpe_ratio !== null ? metrics.sharpe_ratio.toString() : "—"}
            sub={metrics.sharpe_confidence === "high" ? "Statistically significant" : `${metrics.num_trading_days}/60 days for significance`}
            color={
              metrics.sharpe_ratio === null ? "text-zinc-400" :
              metrics.sharpe_ratio >= 1 ? "text-emerald-400" :
              metrics.sharpe_ratio >= 0 ? "text-amber-400" : "text-red-400"
            }
          />
          <MetricCard
            label="Max Drawdown"
            value={`${metrics.max_drawdown_pct}%`}
            sub={`${metrics.max_drawdown_days} days to recover`}
            color={metrics.max_drawdown_pct > -15 ? "text-amber-400" : "text-red-400"}
          />
          <MetricCard
            label="Win Rate"
            value={`${metrics.win_rate_pct}%`}
            sub={metrics.profit_factor ? `Profit factor: ${metrics.profit_factor}` : "Positive days / total days"}
            color={metrics.win_rate_pct >= 55 ? "text-emerald-400" : "text-amber-400"}
          />
        </div>
      )}

      {/* Charts */}
      <div className="space-y-6">
        <EquityCurveChart snapshots={snapshots} />
        <DrawdownChart snapshots={snapshots} />
        <ReturnDistributionChart snapshots={snapshots} />
      </div>

      {/* Additional metrics */}
      {metrics && (
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <MetricCard
            label="Sortino Ratio"
            value={metrics.sortino_ratio !== null ? metrics.sortino_ratio.toString() : "—"}
            sub="Risk-adjusted (downside only)"
            color="text-blue-400"
          />
          <MetricCard
            label="Best Day"
            value={`+${metrics.best_day_pct}%`}
            sub="Largest single-day gain"
            color="text-emerald-400"
          />
          <MetricCard
            label="Worst Day"
            value={`${metrics.worst_day_pct}%`}
            sub="Largest single-day loss"
            color="text-red-400"
          />
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${color}`}>{value}</p>
      <p className="mt-1 text-xs text-zinc-600">{sub}</p>
    </div>
  );
}
