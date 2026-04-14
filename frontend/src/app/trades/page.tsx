"use client";

import { getTrades } from "@/lib/api";
import { Trade } from "@/lib/types";
import { useApiQuery } from "@/lib/useApiQuery";
import Spinner from "@/components/Spinner";
import Tip from "@/components/Tip";
import TradeTable from "@/components/TradeTable";

export default function TradesPage() {
  const { data: trades, loading } = useApiQuery<Trade[]>(
    () => getTrades(200),
    [],
  );

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-primary">Trade History</h1>
            <Tip text="A complete log of every decision the AI has made — buys, sells, and holds. Click any row to see Claude's full reasoning. Blocked trades show why the guardrails stopped them." />
          </div>
          <p className="mt-1 text-sm text-muted">
            Every decision Claude has made, with full reasoning
          </p>
        </div>
        <span className="rounded-lg bg-card-alt px-3 py-1.5 text-sm text-secondary">
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
