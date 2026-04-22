import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TradeTable from "./TradeTable";
import { Trade } from "@/lib/types";

// Mock utils — formatCurrency and formatDateTime depend on Intl / localStorage
vi.mock("@/lib/utils", () => ({
  formatCurrency: (v: number) => `$${v.toFixed(2)}`,
  formatDateTime: (iso: string) => new Date(iso).toISOString().slice(0, 10),
}));

function makeTrade(overrides: Partial<Trade> = {}): Trade {
  return {
    id: 1,
    timestamp: "2026-04-10T14:30:00Z",
    ticker: "AAPL",
    action: "buy",
    quantity: 10,
    price: 175.5,
    claude_reasoning: "Strong earnings outlook",
    confidence: 0.85,
    guardrail_passed: true,
    guardrail_block_reason: null,
    executed: true,
    ...overrides,
  };
}

describe("TradeTable", () => {
  it("renders empty state when no trades", () => {
    render(<TradeTable trades={[]} />);
    expect(screen.getByText("No trades recorded yet")).toBeInTheDocument();
  });

  it("renders table rows with trade data", () => {
    const trades = [
      makeTrade({ id: 1, ticker: "AAPL", quantity: 10, price: 175.5 }),
      makeTrade({ id: 2, ticker: "TSLA", quantity: 5, price: 220.0 }),
    ];
    render(<TradeTable trades={trades} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.getByText("$175.50")).toBeInTheDocument();
    expect(screen.getByText("$220.00")).toBeInTheDocument();
  });

  it('shows "Passed" badge when guardrail passed', () => {
    render(<TradeTable trades={[makeTrade({ guardrail_passed: true })]} />);
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it('shows "Blocked" badge when guardrail failed', () => {
    render(
      <TradeTable
        trades={[
          makeTrade({
            guardrail_passed: false,
            guardrail_block_reason: "Position limit exceeded",
          }),
        ]}
      />,
    );
    expect(screen.getByText("Blocked")).toBeInTheDocument();
  });

  it("displays confidence as percentage", () => {
    render(<TradeTable trades={[makeTrade({ confidence: 0.85 })]} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("displays 0% when confidence is null", () => {
    render(<TradeTable trades={[makeTrade({ confidence: null })]} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("renders BUY action with correct text", () => {
    render(<TradeTable trades={[makeTrade({ action: "buy" })]} />);
    const badge = screen.getByText("buy");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-emerald-900/40");
  });

  it("renders SELL action with correct text and color", () => {
    render(<TradeTable trades={[makeTrade({ action: "sell" })]} />);
    const badge = screen.getByText("sell");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-red-900/40");
  });

  it("renders HOLD action with correct text and color", () => {
    render(<TradeTable trades={[makeTrade({ action: "hold" })]} />);
    const badge = screen.getByText("hold");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-card-alt");
  });

  it("shows dash when price is null", () => {
    render(<TradeTable trades={[makeTrade({ price: null })]} />);
    // The price column should show a dash
    const cells = screen.getAllByText("—");
    expect(cells.length).toBeGreaterThanOrEqual(1);
  });

  it("shows reasoning text", () => {
    render(
      <TradeTable
        trades={[makeTrade({ claude_reasoning: "Strong earnings outlook" })]}
      />,
    );
    expect(screen.getByText("Strong earnings outlook")).toBeInTheDocument();
  });

  it("toggles sort direction on column click", async () => {
    const user = userEvent.setup();
    const trades = [
      makeTrade({ id: 1, ticker: "AAPL", timestamp: "2026-04-10T10:00:00Z" }),
      makeTrade({ id: 2, ticker: "TSLA", timestamp: "2026-04-11T10:00:00Z" }),
    ];
    render(<TradeTable trades={trades} />);

    // Default sort is timestamp desc — click Date header to toggle to asc
    const dateHeader = screen.getByText("Date");
    await user.click(dateHeader);

    // The sort arrow should now show ascending
    expect(screen.getByText("↑")).toBeInTheDocument();
  });
});
