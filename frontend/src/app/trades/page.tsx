"use client";

import { useState } from "react";
import { getTrades, exportTradesCsv } from "@/lib/api";
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
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setExporting(true);
    try {
      await exportTradesCsv(new Date().getFullYear());
    } catch {
      // silently fail — the download just won't happen
    } finally {
      setExporting(false);
    }
  }

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
        <div className="flex items-center gap-3">
          <button
            onClick={handleExport}
            disabled={exporting || trades.length === 0}
            className="flex items-center gap-2 rounded-lg border border-border-strong bg-card-alt px-3 py-1.5 text-sm font-medium text-secondary transition-colors hover:bg-border-strong/30 hover:text-primary disabled:opacity-50"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            {exporting ? "Exporting..." : "Export CSV"}
          </button>
          <span className="rounded-lg bg-card-alt px-3 py-1.5 text-sm text-secondary">
            {trades.length} trade{trades.length !== 1 && "s"}
          </span>
        </div>
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
