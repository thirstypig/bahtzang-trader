"use client";

import { useEffect, useState } from "react";
import { getTrades } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Trade } from "@/lib/types";
import Spinner from "@/components/Spinner";
import TradeTable from "@/components/TradeTable";

export default function TradesPage() {
  const { user } = useAuth();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    getTrades(200)
      .then(setTrades)
      .finally(() => setLoading(false));
  }, [user]);

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
          <Spinner />
        </div>
      ) : (
        <TradeTable trades={trades} />
      )}
    </div>
  );
}
