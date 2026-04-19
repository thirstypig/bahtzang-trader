import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import PlanAllocationChart from "./PlanAllocationChart";
import { InvestmentPlan } from "@/lib/types";

// Mock Recharts — it requires browser APIs that jsdom doesn't fully support
vi.mock("recharts", () => ({
  PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div />,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: () => <div />,
}));

function makePlan(overrides: Partial<InvestmentPlan> = {}): InvestmentPlan {
  return {
    id: 1,
    name: "Test Plan",
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

describe("PlanAllocationChart", () => {
  it("renders nothing with empty plans", () => {
    const { container } = render(<PlanAllocationChart plans={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders chart with plans", () => {
    const plans = [
      makePlan({ id: 1, name: "Growth", budget: 7000 }),
      makePlan({ id: 2, name: "Income", budget: 3000 }),
    ];
    render(<PlanAllocationChart plans={plans} />);
    expect(screen.getByText("Budget Allocation")).toBeInTheDocument();
    expect(screen.getByText("Growth")).toBeInTheDocument();
    expect(screen.getByText("Income")).toBeInTheDocument();
  });

  it("shows total budget in center", () => {
    const plans = [
      makePlan({ id: 1, budget: 7000 }),
      makePlan({ id: 2, budget: 3000 }),
    ];
    render(<PlanAllocationChart plans={plans} />);
    expect(screen.getByText("$10,000.00")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
  });

  it("shows percentage for each plan", () => {
    const plans = [
      makePlan({ id: 1, name: "A", budget: 7500 }),
      makePlan({ id: 2, name: "B", budget: 2500 }),
    ];
    render(<PlanAllocationChart plans={plans} />);
    expect(screen.getByText(/75\.0%/)).toBeInTheDocument();
    expect(screen.getByText(/25\.0%/)).toBeInTheDocument();
  });

  it("calls onSliceClick when legend item is clicked", async () => {
    const onClick = vi.fn();
    const plans = [
      makePlan({ id: 42, name: "Clickable" }),
      makePlan({ id: 43, name: "Other" }),
    ];
    render(<PlanAllocationChart plans={plans} onSliceClick={onClick} />);
    const button = screen.getByText("Clickable").closest("button");
    button?.click();
    expect(onClick).toHaveBeenCalledWith(42);
  });
});
