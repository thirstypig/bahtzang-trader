"use client";

import { Trade } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import Tip from "@/components/Tip";

interface DecisionCardProps {
  trade: Trade | null;
}

function cleanReasoning(text: string | null): string {
  if (!text) return "";
  let cleaned = text.replace(/^Failed to parse Claude response:\s*/i, "");
  cleaned = cleaned.replace(/```json\s*/g, "").replace(/```/g, "");
  if (cleaned.trimStart().startsWith("{") || cleaned.trimStart().startsWith("[")) {
    try {
      const parsed = JSON.parse(cleaned);
      const obj = Array.isArray(parsed) ? parsed[0] : parsed;
      if (obj?.reasoning) return obj.reasoning;
    } catch {
      cleaned = cleaned.replace(/[{}\[\]"]/g, "").replace(/\s+/g, " ").trim();
    }
  }
  return cleaned;
}

const ACTION_STYLES = {
  buy: "bg-pos/15 text-pos border border-pos/30",
  sell: "bg-neg/15 text-neg border border-neg/30",
  hold: "bg-card-alt/40 text-secondary border border-border-strong/30",
};

export default function DecisionCard({ trade }: DecisionCardProps) {
  if (!trade) {
    return (
      <div className="bz-glass p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-medium text-secondary">
            Claude&apos;s Last Decision
          </h2>
          <Tip text="Every trading cycle, the AI analyzes your portfolio and market data, then decides to BUY, SELL, or HOLD." />
        </div>
        <p className="mt-4 text-muted">No decisions yet</p>
      </div>
    );
  }

  const style = ACTION_STYLES[trade.action] || ACTION_STYLES.hold;
  const confidencePct = ((trade.confidence || 0) * 100).toFixed(0);

  return (
    <div className="bz-glass p-6">
      <div className="flex items-start justify-between">
        <h2 className="text-sm font-medium text-secondary">
          Claude&apos;s Last Decision
        </h2>
        <span className="text-xs text-muted">
          {formatDateTime(trade.timestamp)}
        </span>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <span
          className={`rounded-md px-3 py-1 text-sm font-semibold uppercase ${style}`}
        >
          {trade.action}
        </span>
        {trade.ticker && (
          <span className="text-xl font-bold text-primary">{trade.ticker}</span>
        )}
        {trade.quantity > 0 && (
          <span className="text-sm text-secondary">
            &times; {trade.quantity} shares
          </span>
        )}
      </div>

      <div className="mt-4">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-xs text-muted">Confidence <Tip text="How sure the AI is about its decision, from 0% to 100%. Higher confidence means stronger conviction. Trades below the minimum confidence threshold (set in Settings) are blocked." /></span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-card-alt">
            <div
              className="h-full rounded-full bg-pos transition-all"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <span className="text-xs font-medium text-secondary">
            {confidencePct}%
          </span>
        </div>
      </div>

      {trade.claude_reasoning && (
        <div className="bz-glass-soft mt-4 p-4">
          <p className="text-xs font-medium text-muted">Reasoning</p>
          <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-secondary">
            {cleanReasoning(trade.claude_reasoning)}
          </p>
        </div>
      )}

      {!trade.guardrail_passed && trade.guardrail_block_reason && (
        <div className="mt-3 rounded-lg border border-neg/30 bg-neg/10 px-4 py-3">
          <p className="text-xs font-medium text-neg">
            Blocked: {trade.guardrail_block_reason}
          </p>
        </div>
      )}
    </div>
  );
}
