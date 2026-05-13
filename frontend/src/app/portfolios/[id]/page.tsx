"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getPortfolioDetail,
  updatePortfolio,
  runPortfolio,
  exportPortfolioTradesCsv,
  getPortfolioStrategy,
} from "@/lib/api";
import type { InvestmentPlan, Trade, PortfolioStrategy } from "@/lib/types";
import DecisionModeBadge from "@/components/DecisionModeBadge";

const PortfolioEquityCurve = dynamic(
  () => import("@/components/PortfolioEquityCurve"),
  { ssr: false }
);
const TradeTable = dynamic(() => import("@/components/TradeTable"), {
  ssr: false,
});
const PortfolioStrategyForm = dynamic(
  () => import("@/components/PortfolioStrategyForm"),
  { ssr: false }
);
import dynamic from "next/dynamic";

type PortfolioDetailData = InvestmentPlan & { trades: Trade[] };

export default function PortfolioDetailPage() {
  const params = useParams();
  const portfolioId = Number(params.id);

  const [data, setData] = useState<PortfolioDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeTab, setActiveTab] = useState<"overview" | "strategy">(
    "overview"
  );
  const [strategy, setStrategy] = useState<PortfolioStrategy | null>(null);
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [strategyError, setStrategyError] = useState<string | null>(null);

  useEffect(() => {
    refreshPortfolio();
  }, [refreshKey]);

  async function refreshPortfolio() {
    const cancelled = { current: false };

    try {
      setLoading(true);
      setError(null);
      const details = await getPortfolioDetail(portfolioId);
      if (!cancelled.current) {
        setData(details);
      }
    } catch (err) {
      if (!cancelled.current) {
        setError(
          err instanceof Error ? err.message : "Failed to load portfolio"
        );
      }
    } finally {
      if (!cancelled.current) {
        setLoading(false);
      }
    }

    return () => {
      cancelled.current = true;
    };
  }

  async function loadStrategy() {
    try {
      setStrategyLoading(true);
      setStrategyError(null);
      const strat = await getPortfolioStrategy(portfolioId);
      setStrategy(strat);
    } catch (err) {
      setStrategyError(
        err instanceof Error ? err.message : "Failed to load strategy"
      );
    } finally {
      setStrategyLoading(false);
    }
  }

  async function handleToggleActive() {
    if (!data) return;
    try {
      setToggling(true);
      setToggleError(null);
      await updatePortfolio(portfolioId, { is_active: !data.is_active });
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setToggleError(
        err instanceof Error ? err.message : "Failed to toggle portfolio"
      );
    } finally {
      setToggling(false);
    }
  }

  async function handleRunNow() {
    try {
      setRunning(true);
      setRunResult(null);
      const result = await runPortfolio(portfolioId);
      let detail = "";
      if (result.action !== "hold" && result.quantity) {
        const qty = result.quantity % 1 === 0
          ? result.quantity.toString()
          : result.quantity.toFixed(4).replace(/\.?0+$/, "");
        const priceStr = result.price ? ` @ $${result.price.toFixed(2)}` : "";
        detail = ` × ${qty} shares${priceStr}`;
      }
      const label = result.executed
        ? " (executed)"
        : result.action === "hold"
        ? " (no action)"
        : " (blocked)";
      setRunResult(`Trade decision: ${result.action} ${result.ticker}${detail}${label}`);
      setRefreshKey((k) => k + 1);
      setTimeout(() => setRunResult(null), 5000);
    } catch (err) {
      setRunResult(
        err instanceof Error ? err.message : "Failed to run portfolio"
      );
    } finally {
      setRunning(false);
    }
  }

  async function handleExport() {
    try {
      setExporting(true);
      setExportError(null);
      await exportPortfolioTradesCsv(portfolioId);
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : "Failed to export trades"
      );
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8">
        <h1 className="text-3xl font-bold mb-6">Portfolio Details</h1>
        <div className="text-muted">Loading portfolio...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8">
        <Link
          href="/portfolios"
          className="text-accent hover:underline text-sm mb-4 inline-block"
        >
          ← Back to Portfolios
        </Link>
        <div className="p-4 bg-red-100 text-red-800 rounded-lg">
          {error || "Portfolio not found"}
        </div>
      </div>
    );
  }

  const invested = data.budget - data.virtual_cash;
  const investedPct = (invested / data.budget) * 100;

  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-8">
        <div>
          <Link
            href="/portfolios"
            className="text-accent hover:underline text-sm mb-4 inline-block"
          >
            ← Back to Portfolios
          </Link>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-3xl font-bold">{data.name}</h1>
            <DecisionModeBadge
              mode={data.decision_mode ?? "claude_decides"}
              strategyName={data.strategy_id ?? null}
            />
          </div>
          <p className="text-muted mt-2">
            {data.trading_goal} • {data.risk_profile} • {data.trading_frequency}
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleRunNow}
            disabled={running || !data.is_active}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 font-medium text-sm"
          >
            {running ? "Running..." : "Run Now"}
          </button>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors disabled:opacity-50 font-medium text-sm"
          >
            {exporting ? "Exporting..." : "Export CSV"}
          </button>
          <button
            onClick={handleToggleActive}
            disabled={toggling}
            className={`px-4 py-2 rounded-lg transition-colors disabled:opacity-50 font-medium text-sm ${
              data.is_active
                ? "bg-orange-600 text-white hover:bg-orange-700"
                : "bg-green-600 text-white hover:bg-green-700"
            }`}
          >
            {toggling ? "..." : data.is_active ? "Pause" : "Resume"}
          </button>
        </div>
      </div>

      {runResult && (
        <div className="mb-6 p-4 bg-green-100 text-green-800 rounded-lg">
          {runResult}
        </div>
      )}

      {toggleError && (
        <div className="mb-6 p-4 bg-red-100 text-red-800 rounded-lg">
          {toggleError}
        </div>
      )}

      {exportError && (
        <div className="mb-6 p-4 bg-red-100 text-red-800 rounded-lg">
          {exportError}
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-card rounded-lg p-4">
          <p className="text-muted text-sm mb-1">Budget</p>
          <p className="text-2xl font-bold">${data.budget.toLocaleString()}</p>
        </div>
        <div className="bg-card rounded-lg p-4">
          <p className="text-muted text-sm mb-1">Invested</p>
          <p className="text-2xl font-bold text-accent">
            ${invested.toLocaleString()}
          </p>
          <p className="text-xs text-muted mt-1">{investedPct.toFixed(1)}%</p>
        </div>
        <div className="bg-card rounded-lg p-4">
          <p className="text-muted text-sm mb-1">Available</p>
          <p className="text-2xl font-bold">
            ${data.virtual_cash.toLocaleString()}
          </p>
        </div>
        <div className="bg-card rounded-lg p-4">
          <p className="text-muted text-sm mb-1">Status</p>
          <p className="text-2xl font-bold">
            {data.is_active ? (
              <span className="text-green-600">Active</span>
            ) : (
              <span className="text-orange-600">Paused</span>
            )}
          </p>
        </div>
      </div>

      <div className="mb-8">
        <div className="flex gap-4 border-b border-border mb-6">
          <button
            onClick={() => {
              setActiveTab("overview");
            }}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === "overview"
                ? "text-accent border-b-2 border-accent"
                : "text-muted hover:text-primary"
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => {
              setActiveTab("strategy");
              if (!strategy && !strategyLoading) {
                loadStrategy();
              }
            }}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === "strategy"
                ? "text-accent border-b-2 border-accent"
                : "text-muted hover:text-primary"
            }`}
          >
            Trading Rules
          </button>
          <Link
            href={`/portfolios/${portfolioId}/strategy`}
            className="px-4 py-2 font-medium text-muted hover:text-primary transition-colors"
          >
            Decision Engine
          </Link>
          {data.decision_mode === "rules_with_claude_oversight" && (
            <Link
              href={`/portfolios/${portfolioId}/oversight`}
              className="px-4 py-2 font-medium text-muted hover:text-primary transition-colors"
            >
              Oversight
            </Link>
          )}
        </div>

        {activeTab === "overview" && (
          <div className="space-y-8">
            <div className="bg-card rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4">Equity Curve</h2>
              <PortfolioEquityCurve portfolioId={portfolioId} />
            </div>

            <div className="bg-card rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4">Recent Trades</h2>
              <TradeTable trades={data.trades.slice(0, 20)} />
            </div>
          </div>
        )}

        {activeTab === "strategy" && (
          <div className="bg-card rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-6">Trading Rules</h2>
            {strategyLoading ? (
              <div className="text-muted">Loading strategy...</div>
            ) : strategyError ? (
              <div className="p-4 bg-red-100 text-red-800 rounded-lg">
                {strategyError}
              </div>
            ) : strategy ? (
              <PortfolioStrategyForm
                portfolioId={portfolioId}
                strategy={strategy}
                onSave={() => {
                  setRefreshKey((k) => k + 1);
                  loadStrategy();
                }}
              />
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
