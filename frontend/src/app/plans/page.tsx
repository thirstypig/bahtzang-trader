"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { getPlans, deletePlan } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { InvestmentPlan, TradingGoal } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";
import Spinner from "@/components/Spinner";
import Tip from "@/components/Tip";
import ConfirmModal from "@/components/ConfirmModal";
import PlanAllocationChart from "@/components/PlanAllocationChart";

const GOAL_LABELS: Record<TradingGoal, { label: string; icon: string }> = {
  maximize_returns: { label: "Max Returns", icon: "📈" },
  steady_income: { label: "Income", icon: "💰" },
  capital_preservation: { label: "Preserve", icon: "🏦" },
  beat_sp500: { label: "Beat S&P", icon: "🏆" },
  swing_trading: { label: "Swing", icon: "⚡" },
  passive_index: { label: "Passive", icon: "🌊" },
};

const RISK_COLORS: Record<string, string> = {
  conservative: "text-emerald-400",
  moderate: "text-blue-400",
  aggressive: "text-amber-400",
};

export default function PlansPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [plans, setPlans] = useState<InvestmentPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<InvestmentPlan | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function loadPlans() {
    setLoading(true);
    setError(null);
    getPlans()
      .then(setPlans)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load plans"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (user) loadPlans();
  }, [user]);

  const totalBudget = plans.reduce((s, p) => s + p.budget, 0);
  const totalInvested = plans.reduce((s, p) => s + (p.invested ?? 0), 0);

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deletePlan(deleteTarget.id);
      setDeleteTarget(null);
      loadPlans();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete plan");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-primary">Investment Plans</h1>
            <Tip text="Split your portfolio into independent plans, each with its own goal, risk profile, and budget. Like M1 Finance pies — each slice trades independently." />
          </div>
          <p className="mt-1 text-sm text-muted">
            Each plan trades independently with its own budget and strategy
          </p>
        </div>
        <Link
          href="/plans/new"
          className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
        >
          + New Plan
        </Link>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-800 bg-red-950/30 p-6 text-red-400">
          Failed to load plans: {error}
        </div>
      )}

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Spinner />
        </div>
      ) : error ? null : plans.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <p className="text-lg font-medium text-primary">No plans yet</p>
          <p className="mt-2 text-sm text-muted">
            Create your first investment plan to get started. Each plan gets its own budget, goal, and trade history.
          </p>
          <Link
            href="/plans/new"
            className="mt-6 inline-block rounded-lg bg-emerald-600 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
          >
            Create First Plan
          </Link>
        </div>
      ) : (
        <>
          {/* Summary bar */}
          <div className="mb-6 grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted">Total Budget</p>
              <p className="mt-1 text-xl font-bold text-primary">{formatCurrency(totalBudget)}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted">Invested</p>
              <p className="mt-1 text-xl font-bold text-primary">{formatCurrency(totalInvested)}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted">Plans</p>
              <p className="mt-1 text-xl font-bold text-primary">{plans.length}</p>
            </div>
          </div>

          {/* Allocation donut chart */}
          {plans.length >= 2 && (
            <div className="mb-6">
              <PlanAllocationChart
                plans={plans}
                onSliceClick={(id) => router.push(`/plans/${id}`)}
              />
            </div>
          )}

          {/* Plan cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {plans.map((plan) => {
              const goal = GOAL_LABELS[plan.trading_goal] || { label: plan.trading_goal, icon: "📊" };
              const invested = plan.invested ?? 0;
              const investedPct = plan.budget > 0 ? (invested / plan.budget) * 100 : 0;

              return (
                <Link
                  key={plan.id}
                  href={`/plans/${plan.id}`}
                  className="group rounded-xl border border-border bg-card p-5 transition-colors hover:border-border-strong hover:bg-card-alt/30"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{goal.icon}</span>
                      <h3 className="font-semibold text-primary group-hover:text-accent">{plan.name}</h3>
                    </div>
                    {!plan.is_active && (
                      <span className="rounded bg-card-alt px-2 py-0.5 text-[10px] font-medium text-muted">Paused</span>
                    )}
                  </div>

                  <div className="mt-3">
                    <div className="flex items-baseline justify-between">
                      <span className="text-2xl font-bold text-primary">{formatCurrency(plan.budget)}</span>
                      <span className={`text-xs font-medium capitalize ${RISK_COLORS[plan.risk_profile] || "text-secondary"}`}>
                        {plan.risk_profile}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-card-alt">
                      <div
                        className="h-full rounded-full bg-accent transition-all"
                        style={{ width: `${Math.min(investedPct, 100)}%` }}
                      />
                    </div>
                    <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted">
                      <span>{investedPct.toFixed(0)}% invested</span>
                      <span>{plan.trading_frequency}/day</span>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs text-muted">
                    <span>{goal.label}</span>
                    <span>{plan.trade_count ?? 0} trades</span>
                  </div>

                  {plan.target_amount && plan.target_date && (
                    <p className="mt-2 text-[10px] text-accent">
                      Goal: {formatCurrency(plan.target_amount)} by {new Date(plan.target_date + "T00:00:00").toLocaleDateString("en-US", { month: "short", year: "numeric" })}
                    </p>
                  )}

                  <button
                    onClick={(e) => { e.preventDefault(); setDeleteTarget(plan); }}
                    className="mt-3 text-[10px] text-muted transition-colors hover:text-red-400"
                  >
                    Delete
                  </button>
                </Link>
              );
            })}
          </div>
        </>
      )}

      <ConfirmModal
        open={!!deleteTarget}
        title="Delete Plan"
        message={
          deleteError
            ? `Failed to delete: ${deleteError}. Try again?`
            : `Delete "${deleteTarget?.name}"? Trade history will be preserved but the plan and its budget allocation will be removed.`
        }
        confirmLabel={deleting ? "Deleting..." : "Delete Plan"}
        confirmClassName="bg-red-600 hover:bg-red-700"
        onConfirm={handleDelete}
        onCancel={() => {
          setDeleteTarget(null);
          setDeleteError(null);
        }}
      />
    </div>
  );
}
