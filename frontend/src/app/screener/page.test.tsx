import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ScreenerPage from "./page";
import type { ScreenerResult } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getScreener: vi.fn(),
  refreshScreener: vi.fn(),
}));

vi.mock("@/lib/auth", () => {
  // Stable reference so the page's [user] effect dependency doesn't thrash.
  const user = { id: "test-user" };
  return { useAuth: () => ({ user }) };
});

import { getScreener, refreshScreener } from "@/lib/api";
const mockGet = vi.mocked(getScreener);
const mockRefresh = vi.mocked(refreshScreener);

const withCandidates: ScreenerResult = {
  run: { id: 1, run_at: "2026-05-21T11:30:00Z", universe_size: 500, scored_count: 2, status: "complete", error: null },
  candidates: [
    { rank: 1, ticker: "NVDA", composite_score: 1.83, momentum: 0.42, rel_strength: 0.15, trend_score: 1, rsi: 62, volatility: 0.35, price: 900 },
    { rank: 2, ticker: "AAPL", composite_score: 1.12, momentum: 0.2, rel_strength: 0.05, trend_score: 1, rsi: 55, volatility: 0.25, price: 210 },
  ],
};

beforeEach(() => vi.clearAllMocks());

describe("ScreenerPage", () => {
  it("shows empty state when no run has happened", async () => {
    mockGet.mockResolvedValue({ run: null, candidates: [] });
    render(<ScreenerPage />);
    await waitFor(() => expect(screen.getByText(/No screen has run yet/)).toBeInTheDocument());
  });

  it("renders ranked candidates with formatted factors", async () => {
    mockGet.mockResolvedValue(withCandidates);
    render(<ScreenerPage />);
    await waitFor(() => expect(screen.getByText("NVDA")).toBeInTheDocument());
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("+42.0%")).toBeInTheDocument(); // momentum rendered as percent
  });

  it("starts a background refresh and shows a notice", async () => {
    mockGet.mockResolvedValue({ run: null, candidates: [] });
    mockRefresh.mockResolvedValue({ status: "started" });
    render(<ScreenerPage />);
    await waitFor(() => expect(screen.getByText(/No screen has run yet/)).toBeInTheDocument());

    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(mockRefresh).toHaveBeenCalledOnce());
    expect(await screen.findByText(/Screening started/)).toBeInTheDocument();
  });
});
