"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getTrades } from "@/lib/api";
import { Trade } from "@/lib/types";
import Spinner from "@/components/Spinner";
import { formatDateTime } from "@/lib/utils";

interface AuditEntry {
  id: number;
  timestamp: string;
  type: "trade" | "guardrail" | "auth" | "config" | "system";
  severity: "info" | "warning" | "error";
  message: string;
  details: string | null;
}

const SEVERITY_STYLES = {
  info: "text-blue-400 bg-blue-900/20",
  warning: "text-amber-400 bg-amber-900/20",
  error: "text-red-400 bg-red-900/20",
};

const TYPE_STYLES: Record<string, string> = {
  trade: "text-emerald-400",
  guardrail: "text-amber-400",
  auth: "text-blue-400",
  config: "text-purple-400",
  system: "text-zinc-400",
};

function tradesToAuditEntries(trades: Trade[]): AuditEntry[] {
  return trades.map((t) => {
    let type: AuditEntry["type"] = "trade";
    let severity: AuditEntry["severity"] = "info";
    let message = "";

    if (!t.guardrail_passed) {
      type = "guardrail";
      severity = "warning";
      message = `Blocked: ${t.action.toUpperCase()} ${t.ticker} — ${t.guardrail_block_reason}`;
    } else if (t.executed) {
      message = `Executed: ${t.action.toUpperCase()} ${t.quantity} ${t.ticker}${t.price ? ` @ $${t.price.toFixed(2)}` : ""}`;
    } else {
      message = `Decision: ${t.action.toUpperCase()} ${t.ticker || "(hold)"}`;
    }

    return {
      id: t.id,
      timestamp: t.timestamp,
      type,
      severity,
      message,
      details: t.claude_reasoning,
    };
  });
}

export default function AuditLogPage() {
  const { user } = useAuth();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    if (!user) return;
    getTrades(200)
      .then((trades) => setEntries(tradesToAuditEntries(trades)))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [user]);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Audit Log</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Complete trail of every bot action and decision
        </p>
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Spinner />
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center">
          <p className="text-zinc-500">No audit entries yet</p>
        </div>
      ) : (
        <div className="rounded-xl border border-zinc-800 overflow-hidden">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="border-b border-zinc-800/50 bg-zinc-950 transition-colors hover:bg-zinc-900/50"
            >
              <button
                onClick={() =>
                  setExpandedId(expandedId === entry.id ? null : entry.id)
                }
                className="flex w-full items-center gap-4 px-5 py-3 text-left"
              >
                <span className="shrink-0 text-xs text-zinc-500 font-mono w-36">
                  {formatDateTime(entry.timestamp)}
                </span>
                <span
                  className={`shrink-0 w-16 text-[10px] font-semibold uppercase ${TYPE_STYLES[entry.type]}`}
                >
                  {entry.type}
                </span>
                <span
                  className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${SEVERITY_STYLES[entry.severity]}`}
                >
                  {entry.severity}
                </span>
                <span className="flex-1 truncate text-sm text-zinc-300">
                  {entry.message}
                </span>
                <svg
                  className={`h-4 w-4 shrink-0 text-zinc-600 transition-transform ${expandedId === entry.id ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expandedId === entry.id && entry.details && (
                <div className="border-t border-zinc-800/50 bg-zinc-900/30 px-5 py-3">
                  <p className="text-xs font-medium text-zinc-500 mb-1">
                    Claude&apos;s Reasoning
                  </p>
                  <p className="text-sm text-zinc-400 leading-relaxed">
                    {entry.details}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
