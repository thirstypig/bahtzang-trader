import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import KillSwitchButton from "./KillSwitchButton";

vi.mock("@/lib/api", () => ({
  updatePortfolio: vi.fn(),
}));

import { updatePortfolio } from "@/lib/api";
const mockUpdate = vi.mocked(updatePortfolio);

beforeEach(() => {
  mockUpdate.mockReset();
});

describe("KillSwitchButton", () => {
  it('renders "HALT PORTFOLIO" when active', () => {
    render(
      <KillSwitchButton portfolioId={7} isActive={true} onToggled={vi.fn()} />,
    );
    expect(screen.getByText("HALT PORTFOLIO")).toBeInTheDocument();
  });

  it('renders "Resume Trading" when not active', () => {
    render(
      <KillSwitchButton portfolioId={7} isActive={false} onToggled={vi.fn()} />,
    );
    expect(screen.getByText("Resume Trading")).toBeInTheDocument();
    expect(
      screen.getByText("Portfolio Halted — Trading Paused"),
    ).toBeInTheDocument();
  });

  it("PATCHes is_active=false when active and confirmed", async () => {
    const onToggled = vi.fn();
    mockUpdate.mockResolvedValue({} as Awaited<ReturnType<typeof updatePortfolio>>);
    const user = userEvent.setup();

    render(
      <KillSwitchButton portfolioId={7} isActive={true} onToggled={onToggled} />,
    );

    await user.click(screen.getByText("HALT PORTFOLIO"));
    expect(screen.getByText("Yes, halt this portfolio")).toBeInTheDocument();
    await user.click(screen.getByText("Yes, halt this portfolio"));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(7, { is_active: false });
      expect(onToggled).toHaveBeenCalledTimes(1);
    });
  });

  it("PATCHes is_active=true when halted and confirmed", async () => {
    const onToggled = vi.fn();
    mockUpdate.mockResolvedValue({} as Awaited<ReturnType<typeof updatePortfolio>>);
    const user = userEvent.setup();

    render(
      <KillSwitchButton portfolioId={7} isActive={false} onToggled={onToggled} />,
    );

    await user.click(screen.getByText("Resume Trading"));
    expect(screen.getByText("Yes, resume trading")).toBeInTheDocument();
    await user.click(screen.getByText("Yes, resume trading"));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(7, { is_active: true });
      expect(onToggled).toHaveBeenCalledTimes(1);
    });
  });

  it("shows loading state during halt API call", async () => {
    let resolve!: (v: Awaited<ReturnType<typeof updatePortfolio>>) => void;
    mockUpdate.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const user = userEvent.setup();

    render(
      <KillSwitchButton portfolioId={7} isActive={true} onToggled={vi.fn()} />,
    );

    await user.click(screen.getByText("HALT PORTFOLIO"));
    await user.click(screen.getByText("Yes, halt this portfolio"));

    expect(screen.getByText("Halting...")).toBeInTheDocument();

    resolve({} as Awaited<ReturnType<typeof updatePortfolio>>);
    await waitFor(() => {
      expect(screen.queryByText("Halting...")).not.toBeInTheDocument();
    });
  });

  it("closes modal on cancel without calling API", async () => {
    const onToggled = vi.fn();
    const user = userEvent.setup();

    render(
      <KillSwitchButton portfolioId={7} isActive={true} onToggled={onToggled} />,
    );

    await user.click(screen.getByText("HALT PORTFOLIO"));
    expect(screen.getByText("Halt Portfolio")).toBeInTheDocument();
    await user.click(screen.getByText("Cancel"));

    expect(screen.queryByText("Halt Portfolio")).not.toBeInTheDocument();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(onToggled).not.toHaveBeenCalled();
  });
});
