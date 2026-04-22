import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmModal from "./ConfirmModal";

const defaultProps = {
  open: true,
  title: "Delete Item",
  message: "Are you sure you want to delete this?",
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

describe("ConfirmModal", () => {
  it("does not render when open=false", () => {
    const { container } = render(
      <ConfirmModal {...defaultProps} open={false} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders title and message when open=true", () => {
    render(<ConfirmModal {...defaultProps} />);
    expect(screen.getByText("Delete Item")).toBeInTheDocument();
    expect(
      screen.getByText("Are you sure you want to delete this?"),
    ).toBeInTheDocument();
  });

  it("calls onConfirm when confirm button clicked", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<ConfirmModal {...defaultProps} onConfirm={onConfirm} />);

    await user.click(screen.getByText("Confirm"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when cancel button clicked", async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(<ConfirmModal {...defaultProps} onCancel={onCancel} />);

    await user.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows custom confirmLabel", () => {
    render(
      <ConfirmModal {...defaultProps} confirmLabel="Yes, delete forever" />,
    );
    expect(screen.getByText("Yes, delete forever")).toBeInTheDocument();
    // Default "Confirm" label should not be present
    expect(screen.queryByText("Confirm")).not.toBeInTheDocument();
  });

  it("shows default confirmLabel when none provided", () => {
    render(<ConfirmModal {...defaultProps} />);
    expect(screen.getByText("Confirm")).toBeInTheDocument();
  });

  it("calls onCancel when backdrop overlay clicked", async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(<ConfirmModal {...defaultProps} onCancel={onCancel} />);

    // The backdrop is the first fixed inset-0 div with onClick={onCancel}
    const backdrop = document.querySelector(".bg-black\\/60");
    expect(backdrop).toBeTruthy();
    await user.click(backdrop!);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
