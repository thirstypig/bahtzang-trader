import { TradingGoal } from "./types";

/** Canonical goal configuration — single source of truth for labels and icons. */
export const GOAL_CONFIG: Record<TradingGoal, { label: string; icon: string }> = {
  maximize_returns: { label: "Maximize Returns", icon: "📈" },
  steady_income: { label: "Steady Income", icon: "💰" },
  capital_preservation: { label: "Capital Preservation", icon: "🏦" },
  beat_sp500: { label: "Beat S&P 500", icon: "🏆" },
  swing_trading: { label: "Swing Trading", icon: "⚡" },
  passive_index: { label: "Passive Index", icon: "🌊" },
};
