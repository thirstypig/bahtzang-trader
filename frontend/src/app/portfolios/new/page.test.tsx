import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NewPortfolioPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
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
  createPortfolio: vi.fn(),
  getStrategies: vi.fn(),
}));

import { createPortfolio, getStrategies } from "@/lib/api";
const mockCreate = vi.mocked(createPortfolio);
const mockGetStrategies = vi.mocked(getStrategies);

const STRATEGIES = [
  {
    id: "sma_crossover",
    name: "SMA Crossover",
    description: "Golden/death cross",
    params: [
      { key: "fast_period", label: "Fast Period", type: "int", default: 50 },
      { key: "slow_period", label: "Slow Period", type: "int", default: 200 },
    ],
  },
  {
    id: "buy_and_hold",
    name: "Buy and Hold",
    description: "Equal-weight benchmark",
    params: [
      { key: "tickers", label: "Tickers", type: "list", default: [] },
    ],
  },
];

beforeEach(() => {
  mockCreate.mockReset();
  mockGetStrategies.mockReset();
  mockGetStrategies.mockResolvedValue(STRATEGIES);
});

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText(/e.g., Growth Fund/), "Test Portfolio");
  await user.type(screen.getByPlaceholderText("10000"), "5000");
}

describe("NewPortfolioPage — Decision Engine validation", () => {
  it("rules_decide without selecting a strategy shows an error on submit", async () => {
    const user = userEvent.setup();
    render(<NewPortfolioPage />);

    await fillRequiredFields(user);

    // Switch to rules_decide
    await user.click(screen.getByText("Rules decide"));

    // Wait for strategies to load
    await waitFor(() => expect(mockGetStrategies).toHaveBeenCalledOnce());

    // Submit without selecting a strategy
    await user.click(screen.getByText("Create Strategy"));

    expect(
      await screen.findByText("A strategy is required when using Rules or Hybrid mode"),
    ).toBeInTheDocument();
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("rules_with_claude_oversight without strategy also shows error", async () => {
    const user = userEvent.setup();
    render(<NewPortfolioPage />);

    await fillRequiredFields(user);
    await user.click(screen.getByText("Rules + Claude oversight"));
    await waitFor(() => expect(mockGetStrategies).toHaveBeenCalledOnce());

    await user.click(screen.getByText("Create Strategy"));

    expect(
      await screen.findByText("A strategy is required when using Rules or Hybrid mode"),
    ).toBeInTheDocument();
  });

  it("strategy param inputs appear when a strategy with params is selected", async () => {
    const user = userEvent.setup();
    render(<NewPortfolioPage />);

    await user.click(screen.getByText("Rules decide"));
    await waitFor(() => expect(mockGetStrategies).toHaveBeenCalledOnce());

    // Select sma_crossover from the dropdown
    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "sma_crossover");

    // Param inputs should appear
    expect(screen.getByLabelText("Fast Period")).toBeInTheDocument();
    expect(screen.getByLabelText("Slow Period")).toBeInTheDocument();
  });

  it("list-type param input shows 'Comma-separated tickers' hint", async () => {
    const user = userEvent.setup();
    render(<NewPortfolioPage />);

    await user.click(screen.getByText("Rules decide"));
    await waitFor(() => expect(mockGetStrategies).toHaveBeenCalledOnce());

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "buy_and_hold");

    expect(screen.getByText("Comma-separated tickers")).toBeInTheDocument();
  });

  it("claude_decides mode submits without strategy_id", async () => {
    const user = userEvent.setup();
    mockCreate.mockResolvedValue({
      id: 1,
      name: "Test",
      budget: 5000,
      virtual_cash: 5000,
      trading_goal: "maximize_returns",
      risk_profile: "moderate",
      trading_frequency: "1x",
      target_amount: null,
      target_date: null,
      is_active: true,
      created_at: "",
      updated_at: "",
      decision_mode: "claude_decides",
      strategy_id: null,
      strategy_params: {},
    });

    render(<NewPortfolioPage />);
    await fillRequiredFields(user);

    // Default mode is claude_decides — submit directly
    await user.click(screen.getByText("Create Strategy"));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledOnce());
    const call = mockCreate.mock.calls[0][0];
    expect(call.decision_mode).toBe("claude_decides");
    expect(call.strategy_id).toBeNull();
  });
});
