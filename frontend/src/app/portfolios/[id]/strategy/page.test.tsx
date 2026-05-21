import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DecisionEnginePage from "./page";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: mockPush }),
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
  getPortfolioDetail: vi.fn(),
  getStrategies: vi.fn(),
  updatePortfolio: vi.fn(),
}));

import { getPortfolioDetail, getStrategies, updatePortfolio } from "@/lib/api";
const mockGetDetail = vi.mocked(getPortfolioDetail);
const mockGetStrategies = vi.mocked(getStrategies);
const mockUpdate = vi.mocked(updatePortfolio);

const BASE_PORTFOLIO = {
  id: 1,
  name: "Growth Fund",
  budget: 10000,
  virtual_cash: 10000,
  trading_goal: "maximize_returns" as const,
  risk_profile: "moderate" as const,
  trading_frequency: "1x" as const,
  target_amount: null,
  target_date: null,
  is_active: true,
  created_at: "",
  updated_at: "",
  decision_mode: "claude_decides" as const,
  strategy_id: null,
  strategy_params: {},
  trades: [],
};

const STRATEGIES = [
  {
    id: "sma_crossover",
    name: "SMA Crossover",
    description: "Golden/death cross",
    params: [
      { key: "fast_period", label: "Fast Period", type: "int", default: 50 },
    ],
  },
];

beforeEach(() => {
  mockPush.mockReset();
  mockGetDetail.mockReset();
  mockGetStrategies.mockReset();
  mockUpdate.mockReset();
  mockGetStrategies.mockResolvedValue(STRATEGIES);
});

describe("DecisionEnginePage — edit flow", () => {
  it("shows the current decision mode badge on load", async () => {
    mockGetDetail.mockResolvedValue(BASE_PORTFOLIO);
    render(<DecisionEnginePage />);

    await waitFor(() => expect(screen.getByText("Claude")).toBeInTheDocument());
  });

  it("shows confirmation modal when switching from current mode to a different mode", async () => {
    mockGetDetail.mockResolvedValue(BASE_PORTFOLIO);
    const user = userEvent.setup();
    render(<DecisionEnginePage />);

    await waitFor(() => screen.getByText("Claude decides"));

    // Click Rules decide — different from saved mode → modal shown immediately
    await user.click(screen.getByText("Rules decide"));

    await waitFor(() =>
      expect(screen.getByText("Change decision mode?")).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/Changing decision mode will affect future trades only/),
    ).toBeInTheDocument();
  });

  it("applies mode change when user confirms the modal", async () => {
    mockGetDetail.mockResolvedValue(BASE_PORTFOLIO);
    const user = userEvent.setup();
    render(<DecisionEnginePage />);

    await waitFor(() => screen.getByText("Claude decides"));

    await user.click(screen.getByText("Rules decide"));
    await waitFor(() => screen.getByText("Change decision mode?"));

    await user.click(screen.getByText("Yes, change mode"));

    // Modal gone, Rules decide card is now selected
    expect(screen.queryByText("Change decision mode?")).not.toBeInTheDocument();
    // The badge should now show the rules mode label
    expect(screen.getByText("Rules")).toBeInTheDocument();
  });

  it("cancels mode change when user dismisses modal", async () => {
    mockGetDetail.mockResolvedValue(BASE_PORTFOLIO);
    const user = userEvent.setup();
    render(<DecisionEnginePage />);

    await waitFor(() => screen.getByText("Claude decides"));

    await user.click(screen.getByText("Rules decide"));
    await waitFor(() => screen.getByText("Change decision mode?"));

    // Page also has a "Cancel" button — click the backdrop overlay to dismiss the modal
    const backdrop = document.querySelector(".bg-black\\/40");
    await user.click(backdrop!);

    // Mode unchanged — still shows claude_decides
    expect(screen.queryByText("Change decision mode?")).not.toBeInTheDocument();
    expect(screen.getByText("Claude")).toBeInTheDocument();
  });

  it("saves successfully and updates originalMode (no modal on same mode click)", async () => {
    mockGetDetail.mockResolvedValue(BASE_PORTFOLIO);
    mockUpdate.mockResolvedValue({ ...BASE_PORTFOLIO, decision_mode: "claude_decides" });
    const user = userEvent.setup();
    render(<DecisionEnginePage />);

    await waitFor(() => screen.getByText("Claude decides"));

    await user.click(screen.getByText("Save"));

    await waitFor(() =>
      expect(screen.getByText("Decision engine saved.")).toBeInTheDocument(),
    );
    expect(mockUpdate).toHaveBeenCalledWith(1, {
      decision_mode: "claude_decides",
      strategy_id: null,
      strategy_params: {},
    });
  });

  it("saves a manual ticker override (parsed + uppercased) in claude_decides mode", async () => {
    mockGetDetail.mockResolvedValue(BASE_PORTFOLIO);
    mockUpdate.mockResolvedValue(BASE_PORTFOLIO);
    const user = userEvent.setup();
    render(<DecisionEnginePage />);

    await waitFor(() => screen.getByText("Claude decides"));

    await user.type(screen.getByPlaceholderText(/PLTR, COIN, SHOP/), "pltr, coin");
    await user.click(screen.getByText("Save"));

    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(1, {
        decision_mode: "claude_decides",
        strategy_id: null,
        strategy_params: { tickers: ["PLTR", "COIN"] },
      }),
    );
  });

  it("pre-fills the ticker override from existing strategy_params", async () => {
    mockGetDetail.mockResolvedValue({
      ...BASE_PORTFOLIO,
      strategy_params: { tickers: ["NVDA", "AMD"] },
    });
    render(<DecisionEnginePage />);

    await waitFor(() =>
      expect(screen.getByPlaceholderText(/PLTR, COIN, SHOP/)).toHaveValue("NVDA, AMD"),
    );
  });

  it("shows error when rules mode saved without strategy", async () => {
    mockGetDetail.mockResolvedValue({
      ...BASE_PORTFOLIO,
      decision_mode: "rules_decide",
      strategy_id: null,
    });
    mockGetStrategies.mockResolvedValue(STRATEGIES);
    const user = userEvent.setup();
    render(<DecisionEnginePage />);

    await waitFor(() => screen.getByText("Rules decide"));

    // Don't select a strategy, just save
    await user.click(screen.getByText("Save"));

    expect(
      await screen.findByText("A strategy is required when using Rules or Hybrid mode"),
    ).toBeInTheDocument();
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});
