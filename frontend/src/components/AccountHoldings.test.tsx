import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AccountHoldings from "./AccountHoldings";
import { Position } from "@/lib/types";

function makePosition(overrides: Partial<Position> = {}): Position {
  return {
    instrument: { symbol: "AAPL", assetType: "EQUITY" },
    longQuantity: 10,
    marketValue: 1600,
    averagePrice: 150,
    currentDayProfitLoss: 0,
    currentDayProfitLossPercentage: 0,
    ...overrides,
  };
}

describe("AccountHoldings", () => {
  it("shows an empty state when nothing is owned", () => {
    render(<AccountHoldings positions={[]} />);
    expect(screen.getByText(/No holdings yet/)).toBeInTheDocument();
  });

  it("derives cost basis from shares x avg price, not market value", () => {
    // 10 shares @ $150 paid = $1,500 cost basis; worth $1,600 now → +$100 gain.
    render(<AccountHoldings positions={[makePosition()]} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("$1,500.00")).toBeInTheDocument(); // cost basis (row only)
    // market value $1,600.00 shows in both the row and the header total
    expect(screen.getAllByText("$1,600.00").length).toBeGreaterThan(0);
    // gain appears in both the row and the header total
    expect(screen.getAllByText(/\+\$100\.00/).length).toBeGreaterThan(0);
  });

  it("renders fractional share counts without rounding to whole shares", () => {
    render(
      <AccountHoldings
        positions={[makePosition({ longQuantity: 0.2534, marketValue: 40 })]}
      />
    );
    expect(screen.getByText("0.2534")).toBeInTheDocument();
  });

  it("sorts holdings by market value descending", () => {
    const { container } = render(
      <AccountHoldings
        positions={[
          makePosition({ instrument: { symbol: "AAPL", assetType: "EQUITY" }, marketValue: 1000 }),
          makePosition({ instrument: { symbol: "MSFT", assetType: "EQUITY" }, marketValue: 5000 }),
        ]}
      />
    );
    const text = container.textContent ?? "";
    expect(text.indexOf("MSFT")).toBeLessThan(text.indexOf("AAPL"));
  });
});
