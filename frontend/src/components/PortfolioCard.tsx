"use client";

import { Balance, Position } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

interface PortfolioCardProps {
  balance: Balance | null;
  positions: Position[];
}

export default function PortfolioCard({
  balance,
  positions,
}: PortfolioCardProps) {
  const dailyPnL = positions.reduce(
    (sum, p) => sum + (p.currentDayProfitLoss || 0),
    0
  );
  const isPositive = dailyPnL >= 0;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
      <h2 className="text-sm font-medium text-zinc-400">Portfolio Summary</h2>
      <div className="mt-4 grid grid-cols-3 gap-6">
        <div>
          <p className="text-xs text-zinc-500">Total Value</p>
          <p className="mt-1 text-2xl font-bold text-white">
            {balance ? formatCurrency(balance.total_value) : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Cash Available</p>
          <p className="mt-1 text-2xl font-bold text-white">
            {balance ? formatCurrency(balance.cash_available) : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Daily P&L</p>
          <p
            className={`mt-1 text-2xl font-bold ${
              isPositive ? "text-emerald-400" : "text-red-400"
            }`}
          >
            {isPositive ? "+" : ""}
            {formatCurrency(dailyPnL)}
          </p>
        </div>
      </div>
      <div className="mt-4 border-t border-zinc-800 pt-3">
        <p className="text-xs text-zinc-500">
          {positions.length} position{positions.length !== 1 && "s"} held
        </p>
      </div>
    </div>
  );
}
