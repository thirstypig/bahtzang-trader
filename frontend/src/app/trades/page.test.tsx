import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TradesPage from "./page";
import { Trade } from "@/lib/types";

const mockUser = { email: "test@example.com", name: "Test", picture: "" };
vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: mockUser, loading: false, denied: false, signIn: vi.fn(), signOut: vi.fn() })),
}));

vi.mock("@/lib/api", () => ({
  getTrades: vi.fn(),
  exportTradesCsv: vi.fn(),
}));

vi.mock("@/lib/utils", () => ({
  formatCurrency: (v: number) => `$${v.toFixed(2)}`,
  formatDateTime: (iso: string) => new Date(iso).toISOString().slice(0, 10),
}));

import { getTrades, exportTradesCsv } from "@/lib/api";
const mockGetTrades = vi.mocked(getTrades);
const mockExport = vi.mocked(exportTradesCsv);

function makeTrades(n: number): Trade[] {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    timestamp: "2026-04-10T14:30:00Z",
    ticker: `T${i + 1}`,
    action: "buy",
    quantity: 1,
    price: 100,
    claude_reasoning: `reason ${i + 1}`,
    confidence: 0.8,
    guardrail_passed: true,
    guardrail_block_reason: null,
    executed: true,
  }));
}

beforeEach(() => {
  mockGetTrades.mockReset();
  mockExport.mockReset();
});

describe("TradesPage pagination", () => {
  it("shows first 50 trades and 'Showing 1–50 of 120' on initial render", async () => {
    mockGetTrades.mockResolvedValue(makeTrades(120));
    render(<TradesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Showing 1–50 of 120/)).toBeInTheDocument();
    });
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.getByText("T50")).toBeInTheDocument();
    expect(screen.queryByText("T51")).not.toBeInTheDocument();
  });

  it("Next advances to page 2, Previous returns to page 1", async () => {
    mockGetTrades.mockResolvedValue(makeTrades(120));
    render(<TradesPage />);
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Showing 1–50 of 120/));

    await user.click(screen.getByRole("button", { name: /Next/ }));
    expect(screen.getByText(/Showing 51–100 of 120/)).toBeInTheDocument();
    expect(screen.getByText("T51")).toBeInTheDocument();
    expect(screen.queryByText("T1")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Previous/ }));
    expect(screen.getByText(/Showing 1–50 of 120/)).toBeInTheDocument();
  });

  it("clamps the last page label to the trade count, not page-end", async () => {
    mockGetTrades.mockResolvedValue(makeTrades(120));
    render(<TradesPage />);
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Showing 1–50 of 120/));
    await user.click(screen.getByRole("button", { name: /Next/ }));
    await user.click(screen.getByRole("button", { name: /Next/ }));

    // page 3 of 120 — should show 101–120, not 101–150
    expect(screen.getByText(/Showing 101–120 of 120/)).toBeInTheDocument();
  });

  it("disables Previous on page 0 and Next on the last page", async () => {
    mockGetTrades.mockResolvedValue(makeTrades(120));
    render(<TradesPage />);
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Showing 1–50 of 120/));
    expect(screen.getByRole("button", { name: /Previous/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/ })).not.toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Next/ }));
    await user.click(screen.getByRole("button", { name: /Next/ }));
    expect(screen.getByRole("button", { name: /Next/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Previous/ })).not.toBeDisabled();
  });

  it("disables Next when total equals page size exactly (boundary)", async () => {
    mockGetTrades.mockResolvedValue(makeTrades(50));
    render(<TradesPage />);

    await waitFor(() => screen.getByText(/Showing 1–50 of 50/));
    // hasNextPage uses strict >, so exactly 50 trades = no next page
    expect(screen.getByRole("button", { name: /Next/ })).toBeDisabled();
  });

  it("renders an empty state with 0 trades and disables both nav buttons", async () => {
    mockGetTrades.mockResolvedValue([]);
    render(<TradesPage />);

    await waitFor(() => {
      expect(screen.getByText(/No trades recorded yet/)).toBeInTheDocument();
    });
    // count display: "Showing 1–0 of 0" — quirky but truthful, both buttons disabled
    expect(screen.getByRole("button", { name: /Previous/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/ })).toBeDisabled();
  });

  it("requests up to 500 trades on mount (server caps the page-load size)", async () => {
    mockGetTrades.mockResolvedValue(makeTrades(10));
    render(<TradesPage />);
    await waitFor(() => expect(mockGetTrades).toHaveBeenCalledWith(500));
  });
});
