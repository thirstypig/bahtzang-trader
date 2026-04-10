"use client";

import { Trade } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

interface DecisionCardProps {
  trade: Trade | null;
}

const ACTION_STYLES = {
  buy: "bg-emerald-900/40 text-emerald-400 border-emerald-800",
  sell: "bg-red-900/40 text-red-400 border-red-800",
  hold: "bg-zinc-800 text-zinc-300 border-zinc-700",
};

export default function DecisionCard({ trade }: DecisionCardProps) {
  if (!trade) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-sm font-medium text-zinc-400">
          Claude&apos;s Last Decision
        </h2>
        <p className="mt-4 text-zinc-500">No decisions yet</p>
      </div>
    );
  }

  const style = ACTION_STYLES[trade.action] || ACTION_STYLES.hold;
  const confidencePct = ((trade.confidence || 0) * 100).toFixed(0);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
      <div className="flex items-start justify-between">
        <h2 className="text-sm font-medium text-zinc-400">
          Claude&apos;s Last Decision
        </h2>
        <span className="text-xs text-zinc-500">
          {formatDateTime(trade.timestamp)}
        </span>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <span
          className={`rounded-md border px-3 py-1 text-sm font-semibold uppercase ${style}`}
        >
          {trade.action}
        </span>
        {trade.ticker && (
          <span className="text-xl font-bold text-white">{trade.ticker}</span>
        )}
        {trade.quantity > 0 && (
          <span className="text-sm text-zinc-400">
            &times; {trade.quantity} shares
          </span>
        )}
      </div>

      <div className="mt-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">Confidence</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <span className="text-xs font-medium text-zinc-300">
            {confidencePct}%
          </span>
        </div>
      </div>

      {trade.claude_reasoning && (
        <div className="mt-4 rounded-lg bg-zinc-950 p-4">
          <p className="text-xs font-medium text-zinc-500">Reasoning</p>
          <p className="mt-1 text-sm leading-relaxed text-zinc-300">
            {trade.claude_reasoning}
          </p>
        </div>
      )}

      {!trade.guardrail_passed && trade.guardrail_block_reason && (
        <div className="mt-3 rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
          <p className="text-xs font-medium text-red-400">
            Blocked: {trade.guardrail_block_reason}
          </p>
        </div>
      )}
    </div>
  );
}
