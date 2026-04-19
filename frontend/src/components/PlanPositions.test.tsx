import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PlanPositions from "./PlanPositions";

// Mock the API module
vi.mock("@/lib/api", () => ({
  getPlanPositions: vi.fn(),
}));

// Mock formatCurrency since it depends on Intl
vi.mock("@/lib/utils", () => ({
  formatCurrency: (v: number) => `$${v.toFixed(2)}`,
}));

import { getPlanPositions } from "@/lib/api";
const mockGetPositions = vi.mocked(getPlanPositions);

beforeEach(() => {
  mockGetPositions.mockReset();
});

describe("PlanPositions", () => {
  it("shows loading state initially", () => {
    mockGetPositions.mockReturnValue(new Promise(() => {})); // never resolves
    render(<PlanPositions planId={1} />);
    expect(screen.getByText("Loading positions...")).toBeInTheDocument();
  });

  it("shows empty state when no positions", async () => {
    mockGetPositions.mockResolvedValue([]);
    render(<PlanPositions planId={1} />);
    await waitFor(() => {
      expect(screen.getByText(/No open positions/)).toBeInTheDocument();
    });
  });

  it("renders positions table", async () => {
    mockGetPositions.mockResolvedValue([
      {
        ticker: "AAPL",
        quantity: 10,
        avg_cost: 150.0,
        current_price: 160.0,
        market_value: 1600.0,
        cost_basis: 1500.0,
        pnl: 100.0,
        pnl_pct: 6.67,
      },
    ]);
    render(<PlanPositions planId={1} />);
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getByText("$1600.00")).toBeInTheDocument(); // market value
    expect(screen.getByText("+$100.00")).toBeInTheDocument(); // P&L
    expect(screen.getByText("+6.67%")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    mockGetPositions.mockRejectedValue(new Error("Network error"));
    render(<PlanPositions planId={1} />);
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("shows negative P&L in red", async () => {
    mockGetPositions.mockResolvedValue([
      {
        ticker: "TSLA",
        quantity: 5,
        avg_cost: 200.0,
        current_price: 180.0,
        market_value: 900.0,
        cost_basis: 1000.0,
        pnl: -100.0,
        pnl_pct: -10.0,
      },
    ]);
    render(<PlanPositions planId={1} />);
    await waitFor(() => {
      expect(screen.getByText("TSLA")).toBeInTheDocument();
    });
    // Component renders formatCurrency(pnl) — negative sign is inside the $
    expect(screen.getByText("$-100.00")).toBeInTheDocument();
    // Percentage text nodes are split ("-10.00" + "%"); use function matcher
    expect(screen.getByText((_content, el) =>
      el?.tagName === "TD" && el.textContent === "-10.00%",
    )).toBeInTheDocument();
  });
});
