"use client";

import type { DecisionMode } from "@/lib/types";

interface DecisionModeBadgeProps {
  mode: DecisionMode;
  strategyName?: string | null;
}

const BADGE_STYLE: Record<DecisionMode, string> = {
  claude_decides: "bg-accent/15 text-accent",
  rules_decide: "bg-blue-500/15 text-blue-500",
  rules_with_claude_oversight: "bg-teal-500/15 text-teal-500",
};

export function decisionModeLabel(
  mode: DecisionMode,
  strategyName?: string | null,
): string {
  if (mode === "claude_decides") return "Claude";
  const prefix = mode === "rules_decide" ? "Rules" : "Hybrid";
  return strategyName ? `${prefix}: ${strategyName}` : prefix;
}

export default function DecisionModeBadge({
  mode,
  strategyName,
}: DecisionModeBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLE[mode]}`}
    >
      {decisionModeLabel(mode, strategyName)}
    </span>
  );
}
