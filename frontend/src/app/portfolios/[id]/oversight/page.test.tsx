import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import OversightActivityPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  getOversightActivity: vi.fn(),
}));

import { getOversightActivity } from "@/lib/api";
const mockGet = vi.mocked(getOversightActivity);

const EMPTY_RESPONSE = {
  summary: { total: 0, confirmed: 0, overridden: 0, confirmed_pct: 0, overridden_pct: 0 },
  records: [],
};

const CONFIRMED_RECORD = {
  id: 1,
  timestamp: "2026-05-12T10:00:00Z",
  ticker: "AAPL",
  rules_recommendation: { action: "buy", quantity: 5, confidence: 0.75, reasoning: "Golden cross" },
  final_action: "buy",
  executed: true,
  diverged: false,
  claude_reasoning: "Signal is valid [Claude confirmed: consistent with trend]",
};

const OVERRIDDEN_RECORD = {
  id: 2,
  timestamp: "2026-05-12T11:00:00Z",
  ticker: "NVDA",
  rules_recommendation: { action: "buy", quantity: 10, confidence: 0.80, reasoning: "RSI oversold" },
  final_action: "hold",
  executed: false,
  diverged: true,
  claude_reasoning: "[Strategy: RSI oversold] [Claude override: earnings tomorrow]",
};

beforeEach(() => {
  mockGet.mockReset();
});

describe("OversightActivityPage", () => {
  it("shows empty state when no oversight decisions exist", async () => {
    mockGet.mockResolvedValue(EMPTY_RESPONSE);
    render(<OversightActivityPage />);

    await waitFor(() =>
      expect(screen.getByText("No oversight decisions yet")).toBeInTheDocument()
    );
  });

  it("shows summary stat cards when decisions exist", async () => {
    mockGet.mockResolvedValue({
      summary: { total: 4, confirmed: 3, overridden: 1, confirmed_pct: 75.0, overridden_pct: 25.0 },
      records: [CONFIRMED_RECORD, OVERRIDDEN_RECORD],
    });
    render(<OversightActivityPage />);

    await waitFor(() => expect(screen.getByText("Total Decisions")).toBeInTheDocument());
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows 'Confirmed' badge for non-diverged records", async () => {
    mockGet.mockResolvedValue({
      summary: { total: 1, confirmed: 1, overridden: 0, confirmed_pct: 100, overridden_pct: 0 },
      records: [CONFIRMED_RECORD],
    });
    render(<OversightActivityPage />);

    await waitFor(() => expect(screen.getByText("Confirmed")).toBeInTheDocument());
    expect(screen.queryByText("Overridden")).not.toBeInTheDocument();
  });

  it("shows 'Overridden' badge for diverged records", async () => {
    mockGet.mockResolvedValue({
      summary: { total: 1, confirmed: 0, overridden: 1, confirmed_pct: 0, overridden_pct: 100 },
      records: [OVERRIDDEN_RECORD],
    });
    render(<OversightActivityPage />);

    await waitFor(() => expect(screen.getByText("Overridden")).toBeInTheDocument());
    expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
  });

  it("shows ticker and strategy signal action", async () => {
    mockGet.mockResolvedValue({
      summary: { total: 1, confirmed: 1, overridden: 0, confirmed_pct: 100, overridden_pct: 0 },
      records: [CONFIRMED_RECORD],
    });
    render(<OversightActivityPage />);

    await waitFor(() => expect(screen.getByText("AAPL")).toBeInTheDocument());
    // Strategy signal: "buy" label appears twice (once in signal column, once in final column)
    const buyBadges = screen.getAllByText("buy");
    expect(buyBadges.length).toBeGreaterThanOrEqual(2);
  });

  it("shows error message when API fails", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));
    render(<OversightActivityPage />);

    await waitFor(() =>
      expect(screen.getByText("Network error")).toBeInTheDocument()
    );
  });
});
