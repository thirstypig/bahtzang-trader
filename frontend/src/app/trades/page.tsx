"use client";

import { useEffect, useState } from "react";
import { getTrades } from "@/lib/api";
import { Trade } from "@/lib/types";
import TradeTable from "@/components/TradeTable";

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTrades(200)
      .then(setTrades)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Trade History</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Every decision Claude has made, with full reasoning
          </p>
        </div>
        <span className="rounded-lg bg-zinc-800 px-3 py-1.5 text-sm text-zinc-400">
          {trades.length} trade{trades.length !== 1 && "s"}
        </span>
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500" />
        </div>
      ) : (
        <TradeTable trades={trades} />
      )}
    </div>
  );
}
