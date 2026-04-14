"use client";

import { Balance, Position } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";
import Tip from "@/components/Tip";

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
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium text-secondary">Portfolio Summary</h2>
        <Tip text="Your portfolio is the total of all your investments plus uninvested cash. This updates in real-time from your Alpaca brokerage account." />
      </div>
      <div className="mt-4 grid grid-cols-3 gap-6">
        <div>
          <p className="flex items-center gap-1 text-xs text-muted">Total Value <Tip text="Everything you own in your account — stocks + cash combined. This is your net worth in the brokerage." /></p>
          <p className="mt-1 text-2xl font-bold text-primary">
            {balance ? formatCurrency(balance.total_value) : "—"}
          </p>
        </div>
        <div>
          <p className="flex items-center gap-1 text-xs text-muted">Cash Available <Tip text="Money not invested in any stock. The bot uses this cash when it decides to buy something." /></p>
          <p className="mt-1 text-2xl font-bold text-primary">
            {balance ? formatCurrency(balance.cash_available) : "—"}
          </p>
        </div>
        <div>
          <p className="flex items-center gap-1 text-xs text-muted">Daily P&amp;L <Tip text="Profit and Loss for today. Green means your stocks went up today, red means they went down. This resets each trading day." /></p>
          <p
            className={`mt-1 text-2xl font-bold ${
              isPositive ? "text-accent" : "text-red-400"
            }`}
          >
            {isPositive ? "+" : ""}
            {formatCurrency(dailyPnL)}
          </p>
        </div>
      </div>
      <div className="mt-4 border-t border-border pt-3">
        <p className="text-xs text-muted">
          {positions.length} position{positions.length !== 1 && "s"} held
        </p>
      </div>
    </div>
  );
}
