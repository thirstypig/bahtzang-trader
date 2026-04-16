"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getPlan, updatePlan, runPlan, exportPlanTradesCsv } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { InvestmentPlan, Trade } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";
import Spinner from "@/components/Spinner";
import Tip from "@/components/Tip";
import PlanPositions from "@/components/PlanPositions";
import PlanEquityCurve from "@/components/PlanEquityCurve";
import TradeTable from "@/components/TradeTable";

const GOAL_LABELS: Record<string, string> = {
  maximize_returns: "📈 Maximize Returns",
  steady_income: "💰 Steady Income",
  capital_preservation: "🏦 Capital Preservation",
  beat_sp500: "🏆 Beat S&P 500",
  swing_trading: "⚡ Swing Trading",
  passive_index: "🌊 Passive Index",
};

export default function PlanDetailPage() {
  const params = useParams();
  const router = useRouter();
  const planId = Number(params.id);

  const { user } = useAuth();
  const [data, setData] = useState<(InvestmentPlan & { trades: Trade[] }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  function loadPlan() {
    if (Number.isNaN(planId) || planId <= 0) return;
    setLoading(true);
    setError(null);
    getPlan(planId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load plan"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (user) loadPlan();
  }, [user, planId]);

  if (Number.isNaN(planId) || planId <= 0) {
    return <div className="p-8 text-center text-muted">Invalid plan ID</div>;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-8">
        <button onClick={() => router.push("/plans")} className="mb-4 text-xs text-muted transition-colors hover:text-secondary">
          &larr; Back to Plans
        </button>
        <div className="rounded-xl border border-red-800 bg-red-950/30 p-6 text-red-400">
          Failed to load: {error}
        </div>
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const plan = data;
  const trades = data.trades || [];
  const invested = plan.budget - plan.virtual_cash;
  const investedPct = plan.budget > 0 ? (invested / plan.budget) * 100 : 0;

  async function handleToggleActive() {
    setToggling(true);
    setToggleError(null);
    try {
      await updatePlan(planId, { is_active: !plan.is_active });
      loadPlan();
    } catch (err) {
      setToggleError(err instanceof Error ? err.message : "Failed to toggle plan");
    } finally {
      setToggling(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <button onClick={() => router.push("/plans")} className="text-xs text-muted transition-colors hover:text-secondary">
            &larr; Back to Plans
          </button>
          <h1 className="mt-1 text-2xl font-bold text-primary">{plan.name}</h1>
          <p className="mt-1 text-sm text-muted">
            {GOAL_LABELS[plan.trading_goal] || plan.trading_goal} &middot; {plan.risk_profile} &middot; {plan.trading_frequency}/day
          </p>
        </div>
        <button
          onClick={async () => {
            setRunning(true);
            setRunResult(null);
            try {
              const r = await runPlan(planId);
              setRunResult(`${r.action.toUpperCase()} ${r.ticker || ""} — ${r.executed ? "Executed" : "Not executed"}`);
              loadPlan();
            } catch (err) {
              setRunResult(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
            } finally {
              setRunning(false);
            }
          }}
          disabled={running || !plan.is_active}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          {running ? "Running..." : "Run Now"}
        </button>
        <button
          onClick={async () => {
            setExporting(true);
            setExportError(null);
            try {
              await exportPlanTradesCsv(planId);
            } catch (err) {
              setExportError(err instanceof Error ? err.message : "Export failed");
            } finally {
              setExporting(false);
            }
          }}
          disabled={exporting}
          className="flex items-center gap-1.5 rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm font-medium text-secondary transition-colors hover:bg-border-strong/30 hover:text-primary disabled:opacity-50"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          {exporting ? "..." : "CSV"}
        </button>
        <button
          onClick={handleToggleActive}
          disabled={toggling}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
            plan.is_active
              ? "border border-amber-800 bg-amber-900/20 text-amber-400 hover:bg-amber-900/40"
              : "bg-emerald-600 text-white hover:bg-emerald-700"
          }`}
        >
          {toggling ? "..." : plan.is_active ? "Pause Plan" : "Resume Plan"}
        </button>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Budget</p>
          <p className="mt-1 text-xl font-bold text-primary">{formatCurrency(plan.budget)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Virtual Cash</p>
          <p className="mt-1 text-xl font-bold text-primary">{formatCurrency(plan.virtual_cash)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Invested</p>
          <p className="mt-1 text-xl font-bold text-primary">{formatCurrency(invested)}</p>
          <p className="mt-0.5 text-[10px] text-muted">{investedPct.toFixed(0)}% of budget</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Trades</p>
          <p className="mt-1 text-xl font-bold text-primary">{trades.filter((t) => t.executed).length}</p>
          <p className="mt-0.5 text-[10px] text-muted">{trades.length} total decisions</p>
        </div>
      </div>

      {runResult && (
        <div className={`mb-6 rounded-xl px-4 py-3 text-sm ${
          runResult.startsWith("Error") ? "border border-red-800 bg-red-950/30 text-red-400" : "bg-surface text-secondary"
        }`}>
          {runResult}
        </div>
      )}

      {toggleError && (
        <div className="mb-6 rounded-xl border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          Failed to toggle plan: {toggleError}
        </div>
      )}

      {exportError && (
        <div className="mb-6 rounded-xl border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          Failed to export CSV: {exportError}
        </div>
      )}

      {plan.target_amount && plan.target_date && (
        <div className="mb-6 rounded-xl border border-accent/30 bg-accent/5 p-4">
          <p className="text-sm text-accent">
            Timeline Goal: grow to {formatCurrency(plan.target_amount)} by{" "}
            {new Date(plan.target_date + "T00:00:00").toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
          </p>
        </div>
      )}

      {/* Positions + Equity Curve */}
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <PlanPositions planId={planId} />
        <PlanEquityCurve planId={planId} />
      </div>

      {/* Trade History */}
      <div className="rounded-xl border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-4">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-primary">Trade History</h2>
            <Tip text="All decisions made by Claude for this plan. Only executed trades affect your virtual cash." />
          </div>
          {/* Status legend */}
          <div className="flex items-center gap-3 text-[10px]">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-accent" />
              <span className="text-muted">Executed — order placed on Alpaca</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-zinc-400" />
              <span className="text-muted">Hold — Claude chose not to trade</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-red-400" />
              <span className="text-muted">Blocked — guardrails stopped it (hover for reason)</span>
            </span>
          </div>
        </div>
        {trades.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted">
            No trades yet. The bot will start trading when the next scheduled cycle runs.
          </div>
        ) : (
          <TradeTable trades={trades as Trade[]} />
        )}
      </div>
    </div>
  );
}
