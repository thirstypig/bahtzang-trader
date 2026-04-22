import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import KillSwitchButton from "./KillSwitchButton";

// Mock the API module
vi.mock("@/lib/api", () => ({
  activateKillSwitch: vi.fn(),
  deactivateKillSwitch: vi.fn(),
}));

import { activateKillSwitch, deactivateKillSwitch } from "@/lib/api";
const mockActivate = vi.mocked(activateKillSwitch);
const mockDeactivate = vi.mocked(deactivateKillSwitch);

beforeEach(() => {
  mockActivate.mockReset();
  mockDeactivate.mockReset();
});

describe("KillSwitchButton", () => {
  it('renders "KILL SWITCH" button when not active', () => {
    render(<KillSwitchButton isActive={false} onToggled={vi.fn()} />);
    expect(screen.getByText("KILL SWITCH")).toBeInTheDocument();
  });

  it('renders "Resume Trading" when active', () => {
    render(<KillSwitchButton isActive={true} onToggled={vi.fn()} />);
    expect(screen.getByText("Resume Trading")).toBeInTheDocument();
    expect(
      screen.getByText("Kill Switch Active — All Trading Halted"),
    ).toBeInTheDocument();
  });

  it("calls activateKillSwitch API when not active and confirmed", async () => {
    const onToggled = vi.fn();
    mockActivate.mockResolvedValue({ status: "ok" });
    const user = userEvent.setup();

    render(<KillSwitchButton isActive={false} onToggled={onToggled} />);

    // Click the kill switch button to open modal
    await user.click(screen.getByText("KILL SWITCH"));

    // Confirm in the modal
    expect(
      screen.getByText("Yes, halt all trading"),
    ).toBeInTheDocument();
    await user.click(screen.getByText("Yes, halt all trading"));

    await waitFor(() => {
      expect(mockActivate).toHaveBeenCalledTimes(1);
      expect(onToggled).toHaveBeenCalledTimes(1);
    });
  });

  it("calls deactivateKillSwitch API when active and confirmed", async () => {
    const onToggled = vi.fn();
    mockDeactivate.mockResolvedValue({ status: "ok" });
    const user = userEvent.setup();

    render(<KillSwitchButton isActive={true} onToggled={onToggled} />);

    // Click Resume Trading to open modal
    await user.click(screen.getByText("Resume Trading"));

    // Confirm in the modal
    expect(
      screen.getByText("Yes, resume trading"),
    ).toBeInTheDocument();
    await user.click(screen.getByText("Yes, resume trading"));

    await waitFor(() => {
      expect(mockDeactivate).toHaveBeenCalledTimes(1);
      expect(onToggled).toHaveBeenCalledTimes(1);
    });
  });

  it("shows loading state during API call", async () => {
    // Make the API call hang so we can see the loading state
    let resolveActivate!: (v: { status: string }) => void;
    mockActivate.mockReturnValue(
      new Promise((resolve) => {
        resolveActivate = resolve;
      }),
    );
    const user = userEvent.setup();

    render(<KillSwitchButton isActive={false} onToggled={vi.fn()} />);

    // Open the modal and confirm
    await user.click(screen.getByText("KILL SWITCH"));
    await user.click(screen.getByText("Yes, halt all trading"));

    // Button should show loading text
    expect(screen.getByText("Activating...")).toBeInTheDocument();

    // Resolve the promise to clean up
    resolveActivate({ status: "ok" });
    await waitFor(() => {
      expect(screen.queryByText("Activating...")).not.toBeInTheDocument();
    });
  });

  it("shows resume loading state during deactivate API call", async () => {
    let resolveDeactivate!: (v: { status: string }) => void;
    mockDeactivate.mockReturnValue(
      new Promise((resolve) => {
        resolveDeactivate = resolve;
      }),
    );
    const user = userEvent.setup();

    render(<KillSwitchButton isActive={true} onToggled={vi.fn()} />);

    await user.click(screen.getByText("Resume Trading"));
    await user.click(screen.getByText("Yes, resume trading"));

    expect(screen.getByText("Resuming...")).toBeInTheDocument();

    resolveDeactivate({ status: "ok" });
    await waitFor(() => {
      expect(screen.queryByText("Resuming...")).not.toBeInTheDocument();
    });
  });

  it("closes modal on cancel without calling API", async () => {
    const onToggled = vi.fn();
    const user = userEvent.setup();

    render(<KillSwitchButton isActive={false} onToggled={onToggled} />);

    // Open modal
    await user.click(screen.getByText("KILL SWITCH"));
    expect(screen.getByText("Activate Kill Switch")).toBeInTheDocument();

    // Cancel
    await user.click(screen.getByText("Cancel"));

    // Modal should close, API should not be called
    expect(
      screen.queryByText("Activate Kill Switch"),
    ).not.toBeInTheDocument();
    expect(mockActivate).not.toHaveBeenCalled();
    expect(onToggled).not.toHaveBeenCalled();
  });
});
