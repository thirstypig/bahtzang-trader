import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PortfoliosPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("next/dynamic", () => ({
  default: () => () => null,
}));

vi.mock("@/components/DecisionModeBadge", () => ({
  default: ({ mode }: { mode: string }) => <span data-testid="decision-badge">{mode}</span>,
}));

vi.mock("@/lib/api", () => ({
  getPortfolios: vi.fn(),
  deletePortfolio: vi.fn(),
  updatePortfolio: vi.fn(),
}));

import { getPortfolios, deletePortfolio, updatePortfolio } from "@/lib/api";
const mockGet = vi.mocked(getPortfolios);
const mockDelete = vi.mocked(deletePortfolio);
const mockUpdate = vi.mocked(updatePortfolio);

const makePortfolio = (overrides = {}) => ({
  id: 1,
  name: "Test Portfolio",
  budget: 10000,
  virtual_cash: 5000,
  trading_goal: "maximize_returns" as const,
  risk_profile: "aggressive" as const,
  trading_frequency: "5x" as const,
  is_active: true,
  target_amount: null,
  target_date: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  decision_mode: "claude_decides" as const,
  strategy_id: null,
  strategy_params: {},
  trade_count: 5,
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockResolvedValue([makePortfolio()]);
  mockDelete.mockResolvedValue(undefined);
  mockUpdate.mockResolvedValue(makePortfolio({ is_active: false }));
});

describe("PortfoliosPage — pause/resume", () => {
  it("shows 'Pause' in the ⋮ menu for an active portfolio", async () => {
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    expect(screen.getByText("Pause")).toBeInTheDocument();
    expect(screen.queryByText("Resume")).not.toBeInTheDocument();
  });

  it("shows 'Resume' in the ⋮ menu for a paused portfolio", async () => {
    mockGet.mockResolvedValue([makePortfolio({ is_active: false })]);
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    expect(screen.getByText("Resume")).toBeInTheDocument();
    expect(screen.queryByText("Pause")).not.toBeInTheDocument();
  });

  it("calls updatePortfolio with is_active=false when pausing an active portfolio", async () => {
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    fireEvent.click(screen.getByText("Pause"));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledWith(1, { is_active: false }));
  });

  it("calls updatePortfolio with is_active=true when resuming a paused portfolio", async () => {
    mockGet.mockResolvedValue([makePortfolio({ is_active: false })]);
    mockUpdate.mockResolvedValue(makePortfolio({ is_active: true }));
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    fireEvent.click(screen.getByText("Resume"));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalledWith(1, { is_active: true }));
  });

  it("shows 'Paused' badge on an inactive portfolio", async () => {
    mockGet.mockResolvedValue([makePortfolio({ is_active: false })]);
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Paused")).toBeInTheDocument());
  });

  it("does not show 'Paused' badge on an active portfolio", async () => {
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());
    expect(screen.queryByText("Paused")).not.toBeInTheDocument();
  });

  it("closes the ⋮ menu after pause completes", async () => {
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    expect(screen.getByText("Pause")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Pause"));
    await waitFor(() => expect(screen.queryByText("Pause")).not.toBeInTheDocument());
  });
});

describe("PortfoliosPage — delete flow", () => {
  it("shows delete confirm row when Delete is clicked from the menu", async () => {
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    fireEvent.click(screen.getByText("Delete"));

    expect(screen.getByText("Confirm delete")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("calls deletePortfolio and removes the card on confirm", async () => {
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    fireEvent.click(screen.getByText("Delete"));
    fireEvent.click(screen.getByText("Confirm delete"));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(1));
    expect(screen.queryByText("Test Portfolio")).not.toBeInTheDocument();
  });

  it("cancels delete without calling API when Cancel is clicked", async () => {
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Test Portfolio")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Strategy actions"));
    fireEvent.click(screen.getByText("Delete"));
    fireEvent.click(screen.getByText("Cancel"));

    expect(mockDelete).not.toHaveBeenCalled();
    expect(screen.getByText("Test Portfolio")).toBeInTheDocument();
  });
});

describe("PortfoliosPage — loading and error states", () => {
  it("shows loading state initially", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<PortfoliosPage />);
    expect(screen.getByText("Loading strategies...")).toBeInTheDocument();
  });

  it("shows error message when getPortfolios fails", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
  });

  it("shows empty state when no portfolios exist", async () => {
    mockGet.mockResolvedValue([]);
    render(<PortfoliosPage />);
    await waitFor(() => expect(screen.getByText(/No strategies created yet/i)).toBeInTheDocument());
  });
});
