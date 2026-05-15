"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getPortfolios, deletePortfolio, updatePortfolio } from "@/lib/api";
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
  const [menuOpen, setMenuOpen] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pausing, setPausing] = useState<number | null>(null);

  useEffect(() => {
    loadPortfolios();
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    function close(e: MouseEvent) {
      if (!(e.target as Element).closest("[data-portfolio-menu]")) setMenuOpen(null);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

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
      setMenuOpen(null);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete portfolio"
      );
    } finally {
      setDeleting(false);
    }
  }

  async function handleToggleActive(portfolio: InvestmentPlan) {
    try {
      setPausing(portfolio.id);
      const updated = await updatePortfolio(portfolio.id, { is_active: !portfolio.is_active });
      setPortfolios(portfolios.map((p) => (p.id === portfolio.id ? { ...p, is_active: updated.is_active } : p)));
      setMenuOpen(null);
    } catch {
      // silent — detail page has the authoritative kill switch
    } finally {
      setPausing(null);
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
          <div className="mb-8 bz-glass rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Allocation Overview</h2>
            <PortfolioAllocationChart portfolios={portfolios} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {portfolios.map((portfolio) => {
              const invested = portfolio.budget - portfolio.virtual_cash;
              const investedPct = (invested / portfolio.budget) * 100;

              return (
                <div
                  key={portfolio.id}
                  className={`bz-glass rounded-xl p-6 transition-opacity ${!portfolio.is_active ? "opacity-60" : ""}`}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-xl font-bold text-primary">{portfolio.name}</h3>
                        {!portfolio.is_active && (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-border text-muted">
                            Paused
                          </span>
                        )}
                        <DecisionModeBadge
                          mode={portfolio.decision_mode ?? "claude_decides"}
                          strategyName={portfolio.strategy_id ?? null}
                        />
                      </div>
                      <p className="text-sm text-muted">
                        {portfolio.trading_goal}
                      </p>
                    </div>

                    {/* ⋮ menu */}
                    <div className="relative" data-portfolio-menu>
                      {deleteTarget === portfolio.id ? (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDelete(portfolio.id)}
                            disabled={deleting}
                            className="px-3 py-1 text-sm bg-neg text-white rounded-lg hover:opacity-80 disabled:opacity-50"
                          >
                            {deleting ? "..." : "Confirm delete"}
                          </button>
                          <button
                            onClick={() => { setDeleteTarget(null); setMenuOpen(null); }}
                            disabled={deleting}
                            className="px-3 py-1 text-sm text-muted hover:text-primary transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            onClick={() => setMenuOpen(menuOpen === portfolio.id ? null : portfolio.id)}
                            className="p-1.5 text-muted hover:text-primary rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                            aria-label="Portfolio actions"
                          >
                            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                              <circle cx="12" cy="5" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="12" cy="19" r="1.5" />
                            </svg>
                          </button>
                          {menuOpen === portfolio.id && (
                            <div className="absolute right-0 top-full mt-1 w-40 bz-glass-strong rounded-xl shadow-lg py-1 z-10">
                              <button
                                onClick={() => handleToggleActive(portfolio)}
                                disabled={pausing === portfolio.id}
                                className="w-full text-left px-4 py-2 text-sm text-primary hover:bg-accent/10 transition-colors disabled:opacity-50"
                              >
                                {pausing === portfolio.id ? "..." : portfolio.is_active ? "Pause" : "Resume"}
                              </button>
                              <button
                                onClick={() => { setDeleteTarget(portfolio.id); setMenuOpen(null); }}
                                className="w-full text-left px-4 py-2 text-sm text-neg hover:bg-neg/10 transition-colors"
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {deleteError && deleteTarget === portfolio.id && (
                    <div className="mb-4 p-2 bg-neg/10 text-neg text-sm rounded-lg">
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
                    onClick={() => router.push(`/portfolios/${portfolio.id}`)}
                    className="w-full px-4 py-2 bg-accent/90 text-white rounded-lg hover:bg-accent transition-colors font-medium text-sm"
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
