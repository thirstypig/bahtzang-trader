"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getPortfolios, deletePortfolio } from "@/lib/api";
import type { InvestmentPlan } from "@/lib/types";
import DecisionModeBadge from "@/components/DecisionModeBadge";

const PortfolioAllocationChart = dynamic(
  () => import("@/components/PortfolioAllocationChart"),
  { ssr: false }
);

export default function PortfoliosPage() {
  const router = useRouter();
  const [portfolios, setPortfolios] = useState<InvestmentPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    loadPortfolios();
  }, []);

  async function loadPortfolios() {
    try {
      setLoading(true);
      setError(null);
      const data = await getPortfolios();
      setPortfolios(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load portfolios");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      setDeleting(true);
      setDeleteError(null);
      await deletePortfolio(id);
      setPortfolios(portfolios.filter((p) => p.id !== id));
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete portfolio"
      );
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8">
        <h1 className="text-3xl font-bold mb-6">Investment Portfolios</h1>
        <div className="text-muted">Loading portfolios...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Investment Portfolios</h1>
          <p className="text-muted mt-2">
            Manage your portfolio slices with individual budgets and risk
            profiles
          </p>
        </div>
        <Link
          href="/portfolios/new"
          className="px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity"
        >
          + New Portfolio
        </Link>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-100 text-red-800 rounded-lg">
          {error}
        </div>
      )}

      {portfolios.length === 0 ? (
        <div className="text-center py-12 bg-card rounded-lg">
          <p className="text-muted mb-4">No portfolios created yet.</p>
          <Link
            href="/portfolios/new"
            className="text-accent hover:underline font-medium"
          >
            Create your first portfolio
          </Link>
        </div>
      ) : (
        <div>
          <div className="mb-8 bg-card rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Allocation Overview</h2>
            <PortfolioAllocationChart portfolios={portfolios} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {portfolios.map((portfolio) => {
              const invested = portfolio.budget - portfolio.virtual_cash;
              const investedPct = (invested / portfolio.budget) * 100;

              return (
                <div key={portfolio.id} className="bg-card rounded-lg p-6">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-xl font-bold">{portfolio.name}</h3>
                        <DecisionModeBadge
                          mode={portfolio.decision_mode ?? "claude_decides"}
                          strategyName={portfolio.strategy_id ?? null}
                        />
                      </div>
                      <p className="text-sm text-muted">
                        {portfolio.trading_goal}
                      </p>
                    </div>
                    {deleteTarget === portfolio.id ? (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleDelete(portfolio.id)}
                          disabled={deleting}
                          className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                        >
                          {deleting ? "..." : "Confirm"}
                        </button>
                        <button
                          onClick={() => setDeleteTarget(null)}
                          disabled={deleting}
                          className="px-3 py-1 text-sm bg-gray-600 text-white rounded hover:bg-gray-700 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteTarget(portfolio.id)}
                        className="text-muted hover:text-red-600 transition-colors"
                      >
                        ⋮
                      </button>
                    )}
                  </div>

                  {deleteError && deleteTarget === portfolio.id && (
                    <div className="mb-4 p-2 bg-red-100 text-red-800 text-sm rounded">
                      {deleteError}
                    </div>
                  )}

                  <div className="space-y-2 mb-4 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted">Budget</span>
                      <span className="font-medium">
                        ${portfolio.budget.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Invested</span>
                      <span className="font-medium">
                        ${invested.toLocaleString()} ({investedPct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Cash Available</span>
                      <span className="font-medium">
                        ${portfolio.virtual_cash.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Risk Profile</span>
                      <span className="font-medium">
                        {portfolio.risk_profile}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Frequency</span>
                      <span className="font-medium">
                        {portfolio.trading_frequency}
                      </span>
                    </div>
                  </div>

                  <div className="h-1 bg-border rounded-full mb-4 overflow-hidden">
                    <div
                      className="h-full bg-accent transition-all"
                      style={{ width: `${investedPct}%` }}
                    />
                  </div>

                  <button
                    onClick={() =>
                      router.push(`/portfolios/${portfolio.id}`)
                    }
                    className="w-full px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity font-medium"
                  >
                    View Details
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
