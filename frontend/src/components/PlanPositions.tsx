"use client";

import { useEffect, useState } from "react";
import { getPlanPositions } from "@/lib/api";
import { PlanPosition } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

interface PlanPositionsProps {
  planId: number;
}

export default function PlanPositions({ planId }: PlanPositionsProps) {
  const [positions, setPositions] = useState<PlanPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPlanPositions(planId)
      .then(setPositions)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load positions"))
      .finally(() => setLoading(false));
  }, [planId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <h2 className="font-semibold text-primary">Virtual Positions</h2>
        </div>
        <div className="px-6 py-12 text-center text-muted">Loading positions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <h2 className="font-semibold text-primary">Virtual Positions</h2>
        </div>
        <div className="px-6 py-12 text-center text-red-400">{error}</div>
      </div>
    );
  }

  const totalMarketValue = positions.reduce((sum, p) => sum + p.market_value, 0);
  const totalCostBasis = positions.reduce((sum, p) => sum + p.cost_basis, 0);
  const totalPnl = totalMarketValue - totalCostBasis;
  const totalPnlPct = totalCostBasis > 0 ? (totalPnl / totalCostBasis) * 100 : 0;

  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-primary">Virtual Positions</h2>
          {positions.length > 0 && (
            <div className="flex items-center gap-4 text-sm">
              <span className="text-secondary">
                Total: {formatCurrency(totalMarketValue)}
              </span>
              <span className={totalPnl >= 0 ? "text-accent" : "text-red-400"}>
                {totalPnl >= 0 ? "+" : ""}
                {formatCurrency(totalPnl)} ({totalPnlPct >= 0 ? "+" : ""}
                {totalPnlPct.toFixed(2)}%)
              </span>
            </div>
          )}
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="px-6 py-12 text-center text-muted">
          No open positions. The bot will open positions when it executes buy trades.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border/50 bg-card/80">
                <th className="px-4 py-3 text-xs font-medium text-secondary">Ticker</th>
                <th className="px-4 py-3 text-xs font-medium text-secondary text-right">Shares</th>
                <th className="px-4 py-3 text-xs font-medium text-secondary text-right">Avg Cost</th>
                <th className="px-4 py-3 text-xs font-medium text-secondary text-right">Current Price</th>
                <th className="px-4 py-3 text-xs font-medium text-secondary text-right">Market Value</th>
                <th className="px-4 py-3 text-xs font-medium text-secondary text-right">P&L ($)</th>
                <th className="px-4 py-3 text-xs font-medium text-secondary text-right">P&L (%)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {positions.map((pos) => (
                <tr
                  key={pos.ticker}
                  className="bg-surface transition-colors hover:bg-card/50"
                >
                  <td className="px-4 py-3 font-mono font-semibold text-primary">
                    {pos.ticker}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-secondary">
                    {pos.quantity}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-secondary">
                    {formatCurrency(pos.avg_cost)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-secondary">
                    {formatCurrency(pos.current_price)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-secondary">
                    {formatCurrency(pos.market_value)}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-mono font-semibold ${
                      pos.pnl >= 0 ? "text-accent" : "text-red-400"
                    }`}
                  >
                    {pos.pnl >= 0 ? "+" : ""}
                    {formatCurrency(pos.pnl)}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-mono font-semibold ${
                      pos.pnl_pct >= 0 ? "text-accent" : "text-red-400"
                    }`}
                  >
                    {pos.pnl_pct >= 0 ? "+" : ""}
                    {pos.pnl_pct.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
