import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ReportsPage from "./page";
import type { WeeklyReportDetail, WeeklyReportSummary } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getReports: vi.fn(),
  getReport: vi.fn(),
}));

vi.mock("@/lib/auth", () => {
  const user = { id: "test-user" };
  return { useAuth: () => ({ user }) };
});

import { getReport, getReports } from "@/lib/api";
const mockList = vi.mocked(getReports);
const mockDetail = vi.mocked(getReport);

const costs = { spread: 0.7, spread_unpriced_trades: 1, spread_in_fills: true, fees: 0.01, api: 0.1, est_tax: 48, total: 48.11 };
const row = {
  id: 6, name: "Pool A Claude", active: true, start_value: 10000, end_value: 10300,
  return_pct: 3, after_cost_return_pct: 2.5119, spy_return_pct: 1, beat_spy: true,
  since_start: { start_value: 10000, return_pct: 3, after_cost_return_pct: 2.5, spy_return_pct: 5.2, costs },
  trades: 2, wins: 1, losses: 0, win_rate: 100, avg_win: 200, avg_loss: null, costs,
  limit_events: [{ type: "Daily loss halt", count: 2 }],
};
const summary: WeeklyReportSummary = {
  id: 1, week_ending: "2026-11-06", created_at: "2026-11-06T21:20:00Z",
  portfolios: [{ id: 6, name: "Pool A Claude", after_cost_return_pct: 2.5119, spy_return_pct: 1, beat_spy: true }],
};
const detail: WeeklyReportDetail = {
  ...summary,
  payload: { week_ending: "2026-11-06", portfolios: [row], account: { ...row }, assumptions: {} },
  note: "Draft: no change this week — one week is too little data.",
  note_model: "claude-sonnet-4-6",
};

beforeEach(() => vi.clearAllMocks());

describe("ReportsPage", () => {
  it("shows the empty state before the first Friday report", async () => {
    mockList.mockResolvedValue([]);
    render(<ReportsPage />);
    await waitFor(() => expect(screen.getByText(/No reports yet/)).toBeInTheDocument());
    expect(mockDetail).not.toHaveBeenCalled();
  });

  it("renders the latest week: returns vs SPY, costs, limit events, draft note", async () => {
    mockList.mockResolvedValue([summary]);
    mockDetail.mockResolvedValue(detail);
    render(<ReportsPage />);
    await waitFor(() => expect(screen.getAllByText("Pool A Claude").length).toBeGreaterThan(0));
    expect(mockDetail).toHaveBeenCalledWith(1);
    expect(screen.getAllByText("+2.51%").length).toBeGreaterThan(0);   // after costs
    expect(screen.getAllByText("Beat SPY").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Daily loss halt × 2/).length).toBeGreaterThan(0);
    expect(screen.getByText(/one week is too little data/)).toBeInTheDocument();
    expect(screen.getByText(/review before acting/i)).toBeInTheDocument();
    expect(screen.getByText("All portfolios combined")).toBeInTheDocument();
    expect(screen.getByText(/excludes Alpaca positions no portfolio owns/i)).toBeInTheDocument();
    expect(screen.getAllByText(/already in fill prices/i).length).toBeGreaterThan(0);
  });
});
