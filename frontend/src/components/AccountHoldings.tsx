"use client";

import { Position } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";
import Tip from "@/components/Tip";

interface AccountHoldingsProps {
  positions: Position[];
}

/** Format a share count that may be fractional (e.g. 0.0345) without trailing noise. */
function formatShares(qty: number): string {
  return qty.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

/**
 * Account-level holdings table: every position currently owned across the whole
 * Alpaca account, with what was paid (cost basis) vs what it's worth now
 * (market value) and the unrealized gain/loss. This is the real, aggregated
 * "what we own" — per-strategy slices are shown by PortfolioPositions.
 */
export default function AccountHoldings({ positions }: AccountHoldingsProps) {
  const rows = positions
    .map((p) => {
      const shares = p.longQuantity;
      const costBasis = shares * p.averagePrice;
      const marketValue = p.marketValue;
      const pnl = marketValue - costBasis;
      const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
      return {
        symbol: p.instrument.symbol,
        shares,
        avgPrice: p.averagePrice,
        costBasis,
        marketValue,
        pnl,
        pnlPct,
      };
    })
    .sort((a, b) => b.marketValue - a.marketValue);

  const totalCost = rows.reduce((s, r) => s + r.costBasis, 0);
  const totalValue = rows.reduce((s, r) => s + r.marketValue, 0);
  const totalPnl = totalValue - totalCost;
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  return (
    <div className="bz-glass">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-primary">Holdings</h2>
          <Tip text="Every stock you currently own across the whole account: how many shares, what you paid for them, and what they're worth right now." />
        </div>
        {rows.length > 0 && (
          <div className="flex items-center gap-4 text-sm">
            <span className="text-secondary">{formatCurrency(totalValue)}</span>
            <span className={totalPnl >= 0 ? "text-pos" : "text-neg"}>
              {totalPnl >= 0 ? "+" : ""}
              {formatCurrency(totalPnl)} ({totalPnlPct >= 0 ? "+" : ""}
              {totalPnlPct.toFixed(2)}%)
            </span>
          </div>
        )}
      </div>

      {rows.length === 0 ? (
        <div className="px-6 py-12 text-center text-muted">
          No holdings yet — nothing has been bought.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="px-6 py-3 font-medium">Symbol</th>
                <th className="px-6 py-3 text-right font-medium">Shares</th>
                <th className="px-6 py-3 text-right font-medium">Avg Cost</th>
                <th className="px-6 py-3 text-right font-medium">Cost Basis</th>
                <th className="px-6 py-3 text-right font-medium">Market Value</th>
                <th className="px-6 py-3 text-right font-medium">Gain / Loss</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} className="border-t border-border">
                  <td className="px-6 py-3 font-medium text-primary">{r.symbol}</td>
                  <td className="px-6 py-3 text-right text-secondary">{formatShares(r.shares)}</td>
                  <td className="px-6 py-3 text-right text-secondary">{formatCurrency(r.avgPrice)}</td>
                  <td className="px-6 py-3 text-right text-secondary">{formatCurrency(r.costBasis)}</td>
                  <td className="px-6 py-3 text-right text-primary">{formatCurrency(r.marketValue)}</td>
                  <td className={`px-6 py-3 text-right ${r.pnl >= 0 ? "text-pos" : "text-neg"}`}>
                    {r.pnl >= 0 ? "+" : ""}
                    {formatCurrency(r.pnl)} ({r.pnlPct >= 0 ? "+" : ""}
                    {r.pnlPct.toFixed(2)}%)
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
