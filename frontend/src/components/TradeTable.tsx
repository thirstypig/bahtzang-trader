"use client";

import { useState } from "react";
import { Trade } from "@/lib/types";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import Tip from "@/components/Tip";

interface TradeTableProps {
  trades: Trade[];
}

type SortKey = keyof Trade;
type SortDir = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; className?: string; tip?: string }[] = [
  { key: "timestamp", label: "Date", tip: "When the bot made this decision" },
  { key: "ticker", label: "Ticker", tip: "The stock symbol (e.g., AAPL = Apple)" },
  { key: "action", label: "Action", tip: "BUY = purchase shares, SELL = sell shares you own, HOLD = do nothing" },
  { key: "quantity", label: "Qty", className: "text-right", tip: "Number of shares bought or sold" },
  { key: "price", label: "Price", className: "text-right", tip: "Price per share at the time of the trade" },
  { key: "confidence", label: "Confidence", className: "text-right", tip: "How sure the AI was about this decision (0-100%). Trades below the minimum threshold get blocked." },
  { key: "guardrail_passed", label: "Guardrail", tip: "Did the trade pass safety checks? 'Blocked' means guardrails prevented it — for example, exceeding position limits." },
  { key: "claude_reasoning", label: "Reasoning", tip: "The AI's explanation for why it made this decision" },
];

const ACTION_BADGE: Record<string, string> = {
  buy: "bg-emerald-900/40 text-emerald-400",
  sell: "bg-red-900/40 text-red-400",
  hold: "bg-zinc-800 text-zinc-400",
};

export default function TradeTable({ trades }: TradeTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = [...trades].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;

    let cmp: number;
    if (typeof aVal === "string" && typeof bVal === "string") {
      cmp = aVal.localeCompare(bVal);
    } else {
      cmp = Number(aVal) - Number(bVal);
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/80">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className={`cursor-pointer whitespace-nowrap px-4 py-3 text-xs font-medium text-zinc-400 transition-colors hover:text-white ${col.className || ""}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {col.tip && <Tip text={col.tip} position="bottom" />}
                  </span>
                  {sortKey === col.key && (
                    <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {sorted.map((trade) => (
              <tr
                key={trade.id}
                className="bg-zinc-950 transition-colors hover:bg-zinc-900/50"
              >
                <td className="whitespace-nowrap px-4 py-3 text-zinc-300">
                  {formatDateTime(trade.timestamp)}
                </td>
                <td className="px-4 py-3 font-mono font-semibold text-white">
                  {trade.ticker || "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase ${ACTION_BADGE[trade.action] || ACTION_BADGE.hold}`}
                  >
                    {trade.action}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-zinc-300">
                  {trade.quantity}
                </td>
                <td className="px-4 py-3 text-right font-mono text-zinc-300">
                  {trade.price ? formatCurrency(trade.price) : "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  <ConfidenceBar value={trade.confidence} />
                </td>
                <td className="px-4 py-3">
                  <GuardrailBadge
                    passed={trade.guardrail_passed}
                    reason={trade.guardrail_block_reason}
                  />
                </td>
                <td className="max-w-xs truncate px-4 py-3 text-zinc-400">
                  {trade.claude_reasoning || "—"}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-zinc-500">
                  No trades recorded yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number | null }) {
  const pct = ((value || 0) * 100).toFixed(0);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full bg-emerald-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-zinc-400">{pct}%</span>
    </div>
  );
}

function GuardrailBadge({
  passed,
  reason,
}: {
  passed: boolean;
  reason: string | null;
}) {
  if (passed) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
        <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
            clipRule="evenodd"
          />
        </svg>
        Passed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-red-400" title={reason || ""}>
      <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
          clipRule="evenodd"
        />
      </svg>
      Blocked
    </span>
  );
}
