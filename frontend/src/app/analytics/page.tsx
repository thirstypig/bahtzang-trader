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
import Tip from "@/components/Tip";
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
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-primary">Analytics</h1>
            <Tip text="This page measures how well the bot is performing. Metrics update daily from portfolio snapshots. More data points = more reliable metrics. You need at least 60 days for the Sharpe ratio to be statistically meaningful." />
          </div>
          <p className="mt-1 text-sm text-muted">
            Performance metrics and portfolio analysis
            {snapshots.length > 0 && ` — ${snapshots.length} daily snapshots`}
          </p>
        </div>
        <button
          onClick={handleTakeSnapshot}
          disabled={snapshotting}
          className="rounded-lg border border-border-strong bg-card-alt px-4 py-2 text-xs font-medium text-secondary transition-colors hover:bg-border-strong disabled:opacity-50"
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
          color="text-primary"
          tip="Every time the bot runs, it makes a decision — buy, sell, or hold. This counts ALL decisions, including holds (doing nothing)."
        />
        <MetricCard
          label="Executed Trades"
          value={executed.length.toString()}
          sub={`${blocked.length} blocked by guardrails`}
          color="text-accent"
          tip="Trades that actually went through. Some trades get blocked by guardrails (safety rules) — for example, if the bot tries to invest too much money at once."
        />
        <MetricCard
          label="Avg Confidence"
          value={`${(avgConfidence * 100).toFixed(1)}%`}
          sub="Claude's average conviction"
          color="text-blue-400"
          tip="The AI rates each decision from 0-100%. Higher means it's more sure. If this is consistently low, the bot is uncertain about its trades."
        />
        <MetricCard
          label="Snapshots"
          value={snapshots.length.toString()}
          sub={snapshots.length >= 60 ? "Sharpe is significant" : `${snapshots.length}/60 for Sharpe significance`}
          color={snapshots.length >= 60 ? "text-accent" : "text-amber-400"}
          tip="A snapshot records your portfolio value at the end of each trading day. You need at least 60 snapshots (about 3 months) for the performance metrics to be statistically reliable."
        />
      </div>

      {/* Portfolio Metrics (from snapshots) */}
      {metrics && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Total Return"
            value={`${metrics.total_return_pct >= 0 ? "+" : ""}${metrics.total_return_pct}%`}
            sub={`Over ${metrics.num_trading_days} trading days`}
            color={metrics.total_return_pct >= 0 ? "text-accent" : "text-red-400"}
            tip="How much your portfolio has grown (or shrunk) since the bot started. For example, +5% means $100,000 became $105,000."
          />
          <MetricCard
            label={`Sharpe Ratio${metrics.sharpe_confidence !== "high" ? ` (${metrics.sharpe_confidence})` : ""}`}
            value={metrics.sharpe_ratio !== null ? metrics.sharpe_ratio.toString() : "—"}
            sub={metrics.sharpe_confidence === "high" ? "Statistically significant" : `${metrics.num_trading_days}/60 days for significance`}
            color={
              metrics.sharpe_ratio === null ? "text-secondary" :
              metrics.sharpe_ratio >= 1 ? "text-accent" :
              metrics.sharpe_ratio >= 0 ? "text-amber-400" : "text-red-400"
            }
            tip="Measures return per unit of risk. Think of it as 'bang for your buck.' Above 1.0 is good, above 2.0 is excellent. Below 0 means you're losing money. Needs 60+ days of data to be reliable."
          />
          <MetricCard
            label="Max Drawdown"
            value={`${metrics.max_drawdown_pct}%`}
            sub={`${metrics.max_drawdown_days} days to recover`}
            color={metrics.max_drawdown_pct > -15 ? "text-amber-400" : "text-red-400"}
            tip="The worst peak-to-trough drop. If your portfolio went from $100K to $90K, that's a -10% drawdown. Smaller is better. This tells you the worst-case scenario so far."
          />
          <MetricCard
            label="Win Rate"
            value={`${metrics.win_rate_pct}%`}
            sub={metrics.profit_factor ? `Profit factor: ${metrics.profit_factor}` : "Positive days / total days"}
            color={metrics.win_rate_pct >= 55 ? "text-accent" : "text-amber-400"}
            tip="Percentage of days your portfolio went up. 55%+ is good — even the best traders don't win every day. What matters is that wins are bigger than losses."
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
            tip="Like Sharpe ratio but only penalizes downside volatility (bad days). A high Sortino means good returns without many bad days. More useful than Sharpe if your returns are mostly positive."
          />
          <MetricCard
            label="Best Day"
            value={`+${metrics.best_day_pct}%`}
            sub="Largest single-day gain"
            color="text-accent"
            tip="Your single best day. Nice to see, but don't count on it repeating. Consistent small wins beat occasional big ones."
          />
          <MetricCard
            label="Worst Day"
            value={`${metrics.worst_day_pct}%`}
            sub="Largest single-day loss"
            color="text-red-400"
            tip="Your single worst day. This is the pain threshold. If this number is bigger than you're comfortable with, consider switching to a more conservative risk profile in Settings."
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
  tip,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
  tip?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <p className="flex items-center gap-1 text-xs text-muted">
        {label}
        {tip && <Tip text={tip} />}
      </p>
      <p className={`mt-2 text-3xl font-bold ${color}`}>{value}</p>
      <p className="mt-1 text-xs text-muted">{sub}</p>
    </div>
  );
}
