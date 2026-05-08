import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import PortfolioAllocationChart from "./PortfolioAllocationChart";
import { InvestmentPlan } from "@/lib/types";

// Mock Recharts — it requires browser APIs that jsdom doesn't fully support
vi.mock("recharts", () => ({
  PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div />,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: () => <div />,
}));

function makePortfolio(overrides: Partial<InvestmentPlan> = {}): InvestmentPlan {
  return {
    id: 1,
    name: "Test Portfolio",
    budget: 5000,
    virtual_cash: 5000,
    trading_goal: "maximize_returns",
    risk_profile: "moderate",
    trading_frequency: "1x",
    target_amount: null,
    target_date: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("PortfolioAllocationChart", () => {
  it("renders nothing with empty portfolios", () => {
    const { container } = render(<PortfolioAllocationChart portfolios={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders chart with portfolios", () => {
    const portfolios = [
      makePortfolio({ id: 1, name: "Growth", budget: 7000 }),
      makePortfolio({ id: 2, name: "Income", budget: 3000 }),
    ];
    render(<PortfolioAllocationChart portfolios={portfolios} />);
    expect(screen.getByText("Budget Allocation")).toBeInTheDocument();
    expect(screen.getByText("Growth")).toBeInTheDocument();
    expect(screen.getByText("Income")).toBeInTheDocument();
  });

  it("shows total budget in center", () => {
    const portfolios = [
      makePortfolio({ id: 1, budget: 7000 }),
      makePortfolio({ id: 2, budget: 3000 }),
    ];
    render(<PortfolioAllocationChart portfolios={portfolios} />);
    expect(screen.getByText("$10,000.00")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
  });

  it("shows percentage for each portfolio", () => {
    const portfolios = [
      makePortfolio({ id: 1, name: "A", budget: 7500 }),
      makePortfolio({ id: 2, name: "B", budget: 2500 }),
    ];
    render(<PortfolioAllocationChart portfolios={portfolios} />);
    expect(screen.getByText(/75\.0%/)).toBeInTheDocument();
    expect(screen.getByText(/25\.0%/)).toBeInTheDocument();
  });

  it("calls onSliceClick when legend item is clicked", async () => {
    const onClick = vi.fn();
    const portfolios = [
      makePortfolio({ id: 42, name: "Clickable" }),
      makePortfolio({ id: 43, name: "Other" }),
    ];
    render(<PortfolioAllocationChart portfolios={portfolios} onSliceClick={onClick} />);
    const button = screen.getByText("Clickable").closest("button");
    button?.click();
    expect(onClick).toHaveBeenCalledWith(42);
  });
});
