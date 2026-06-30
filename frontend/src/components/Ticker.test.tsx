import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Ticker from "./Ticker";
import { CompanyProfile } from "@/lib/types";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({ getCompanyProfile: vi.fn() }));
const getCompanyProfile = vi.mocked(api.getCompanyProfile);

function profile(overrides: Partial<CompanyProfile> = {}): CompanyProfile {
  return {
    ticker: "AAPL",
    name: "Apple Inc",
    industry: "Technology",
    exchange: "NASDAQ",
    market_cap: 3_200_000,
    logo: null,
    currency: "USD",
    website: null,
    yahoo_url: "https://finance.yahoo.com/quote/AAPL",
    source: "finnhub",
    ...overrides,
  };
}

describe("Ticker", () => {
  beforeEach(() => getCompanyProfile.mockReset());

  it("renders the symbol", () => {
    render(<Ticker symbol="AAPL" />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });

  it("renders an em dash and no card for an empty symbol", () => {
    render(<Ticker symbol={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(getCompanyProfile).not.toHaveBeenCalled();
  });

  it("fetches the profile on hover and shows company info + Yahoo link", async () => {
    getCompanyProfile.mockResolvedValue(profile());
    const user = userEvent.setup();
    render(<Ticker symbol="AAPL" />);

    await user.hover(screen.getByText("AAPL"));

    await waitFor(() =>
      expect(screen.getByText("Apple Inc")).toBeInTheDocument(),
    );
    expect(screen.getByText("Technology")).toBeInTheDocument();
    expect(screen.getByText(/Market cap \$3\.2T/)).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /Yahoo Finance/ });
    expect(link).toHaveAttribute("href", "https://finance.yahoo.com/quote/AAPL");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("fetches only once across repeated hovers", async () => {
    getCompanyProfile.mockResolvedValue(profile());
    const user = userEvent.setup();
    render(<Ticker symbol="AAPL" />);

    await user.hover(screen.getByText("AAPL"));
    await waitFor(() => expect(getCompanyProfile).toHaveBeenCalledTimes(1));
    await user.unhover(screen.getByText("AAPL"));
    await user.hover(screen.getByText("AAPL"));

    expect(getCompanyProfile).toHaveBeenCalledTimes(1);
  });

  it("shows a Yahoo link (dash form) for crypto with no company metadata", async () => {
    // The backend returns a resolved source:"none" profile for crypto pairs —
    // no name/industry, but always a usable Yahoo URL.
    getCompanyProfile.mockResolvedValue(
      profile({
        ticker: "BTC/USD",
        name: null,
        industry: "Cryptocurrency",
        exchange: null,
        market_cap: null,
        currency: null,
        yahoo_url: "https://finance.yahoo.com/quote/BTC-USD",
        source: "none",
      }),
    );
    const user = userEvent.setup();
    render(<Ticker symbol="BTC/USD" />);

    await user.hover(screen.getByText("BTC/USD"));

    await waitFor(() => {
      const link = screen.getByRole("link", { name: /Yahoo Finance/ });
      expect(link).toHaveAttribute(
        "href",
        "https://finance.yahoo.com/quote/BTC-USD",
      );
    });
  });
});
