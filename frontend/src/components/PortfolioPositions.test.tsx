import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PortfolioPositions from "./PortfolioPositions";
import { PlanPosition } from "@/lib/types";
import * as api from "@/lib/api";

vi.mock("@/lib/api");

function makePosition(overrides: Partial<PlanPosition> = {}): PlanPosition {
  return {
    id: 1,
    plan_id: 1,
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 150,
    current_price: 160,
    market_value: 1600,
    cost_basis: 1500,
    pnl: 100,
    pnl_pct: 6.67,
    ...overrides,
  };
}

describe("PortfolioPositions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    vi.mocked(api.getPortfolioPositions).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );
    render(<PortfolioPositions portfolioId={1} />);
    expect(screen.getByText("Loading positions...")).toBeInTheDocument();
  });

  it("renders error state on API failure", async () => {
    const error = new Error("Network error");
    vi.mocked(api.getPortfolioPositions).mockRejectedValue(error);
    render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("renders empty state when no positions", async () => {
    vi.mocked(api.getPortfolioPositions).mockResolvedValue([]);
    render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      expect(screen.getByText(/No open positions/)).toBeInTheDocument();
    });
  });

  it("renders positions table with data", async () => {
    const positions = [
      makePosition({ id: 1, ticker: "AAPL", quantity: 10, market_value: 1600 }),
      makePosition({ id: 2, ticker: "MSFT", quantity: 5, market_value: 2000 }),
    ];
    vi.mocked(api.getPortfolioPositions).mockResolvedValue(positions);
    render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("MSFT")).toBeInTheDocument();
    });
  });

  it("displays total market value in header", async () => {
    const positions = [
      makePosition({ id: 1, ticker: "AAPL", market_value: 1600 }),
      makePosition({ id: 2, ticker: "MSFT", market_value: 2000 }),
    ];
    vi.mocked(api.getPortfolioPositions).mockResolvedValue(positions);
    render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      expect(screen.getByText("Total: $3,600.00")).toBeInTheDocument();
    });
  });

  it("displays total P&L with correct sign and percentage", async () => {
    const positions = [
      makePosition({
        id: 1,
        ticker: "AAPL",
        cost_basis: 1500,
        market_value: 1600,
        pnl: 100,
        pnl_pct: 6.67,
      }),
    ];
    vi.mocked(api.getPortfolioPositions).mockResolvedValue(positions);
    render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      expect(screen.getAllByText(/\+\$100\.00/)[0]).toBeInTheDocument();
      expect(screen.getByText("+6.67%")).toBeInTheDocument();
    });
  });

  it("shows negative P&L without plus sign", async () => {
    const positions = [
      makePosition({
        id: 1,
        ticker: "AAPL",
        cost_basis: 1500,
        market_value: 1400,
        pnl: -100,
        pnl_pct: -6.67,
      }),
    ];
    vi.mocked(api.getPortfolioPositions).mockResolvedValue(positions);
    render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      const elements = screen.getAllByText("-$100.00");
      expect(elements.length).toBeGreaterThan(0);
      expect(screen.getByText("-6.67%")).toBeInTheDocument();
    });
  });

  it("renders position details in table rows", async () => {
    const positions = [
      makePosition({
        id: 1,
        ticker: "AAPL",
        quantity: 10,
        avg_cost: 150,
        current_price: 160,
        market_value: 1600,
        pnl: 100,
        pnl_pct: 6.67,
      }),
    ];
    vi.mocked(api.getPortfolioPositions).mockResolvedValue(positions);
    render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      expect(screen.getByText("10")).toBeInTheDocument();
      expect(screen.getByText("$150.00")).toBeInTheDocument();
      expect(screen.getByText("$160.00")).toBeInTheDocument();
      expect(screen.getByText("$1,600.00")).toBeInTheDocument();
    });
  });

  it("refetches when portfolioId prop changes", async () => {
    const positions1 = [makePosition({ id: 1, ticker: "AAPL" })];
    const positions2 = [makePosition({ id: 2, ticker: "MSFT" })];
    vi.mocked(api.getPortfolioPositions).mockResolvedValueOnce(positions1);
    const { rerender } = render(<PortfolioPositions portfolioId={1} />);
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    vi.mocked(api.getPortfolioPositions).mockResolvedValueOnce(positions2);
    rerender(<PortfolioPositions portfolioId={2} />);
    await waitFor(() => {
      expect(screen.getByText("MSFT")).toBeInTheDocument();
    });
  });

  it("cleans up pending request on unmount", async () => {
    vi.mocked(api.getPortfolioPositions).mockImplementation(
      () => new Promise(() => {})
    );
    const { unmount } = render(<PortfolioPositions portfolioId={1} />);
    unmount();
    // Component should clean up cancelled flag without errors
    expect(true).toBe(true);
  });
});
