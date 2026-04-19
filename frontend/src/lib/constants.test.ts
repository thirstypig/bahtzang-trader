import { describe, it, expect } from "vitest";
import { GOAL_CONFIG } from "./constants";
import { TradingGoal } from "./types";

describe("GOAL_CONFIG", () => {
  const ALL_GOALS: TradingGoal[] = [
    "maximize_returns",
    "steady_income",
    "capital_preservation",
    "beat_sp500",
    "swing_trading",
    "passive_index",
  ];

  it("has an entry for every TradingGoal", () => {
    for (const goal of ALL_GOALS) {
      expect(GOAL_CONFIG[goal]).toBeDefined();
      expect(GOAL_CONFIG[goal].label).toBeTruthy();
      expect(GOAL_CONFIG[goal].icon).toBeTruthy();
    }
  });

  it("has unique labels", () => {
    const labels = Object.values(GOAL_CONFIG).map((g) => g.label);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("has unique icons", () => {
    const icons = Object.values(GOAL_CONFIG).map((g) => g.icon);
    expect(new Set(icons).size).toBe(icons.length);
  });
});
