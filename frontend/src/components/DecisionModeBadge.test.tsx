import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DecisionModeBadge from "./DecisionModeBadge";

describe("DecisionModeBadge", () => {
  it("renders 'Claude' for claude_decides", () => {
    render(<DecisionModeBadge mode="claude_decides" />);
    expect(screen.getByText("Claude")).toBeInTheDocument();
  });

  it("renders 'Claude' for claude_decides even with strategyName provided", () => {
    render(<DecisionModeBadge mode="claude_decides" strategyName="SMA Crossover" />);
    expect(screen.getByText("Claude")).toBeInTheDocument();
  });

  it("renders 'Rules: SMA Crossover' for rules_decide with strategyName", () => {
    render(<DecisionModeBadge mode="rules_decide" strategyName="SMA Crossover" />);
    expect(screen.getByText("Rules: SMA Crossover")).toBeInTheDocument();
  });

  it("renders 'Rules' for rules_decide without strategyName", () => {
    render(<DecisionModeBadge mode="rules_decide" />);
    expect(screen.getByText("Rules")).toBeInTheDocument();
  });

  it("renders 'Hybrid: Dual Momentum' for rules_with_claude_oversight with strategyName", () => {
    render(
      <DecisionModeBadge mode="rules_with_claude_oversight" strategyName="Dual Momentum" />,
    );
    expect(screen.getByText("Hybrid: Dual Momentum")).toBeInTheDocument();
  });

  it("renders 'Hybrid' for rules_with_claude_oversight without strategyName", () => {
    render(<DecisionModeBadge mode="rules_with_claude_oversight" />);
    expect(screen.getByText("Hybrid")).toBeInTheDocument();
  });
});
