import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TopNav from "./TopNav";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ theme: "dark", toggle: vi.fn() }),
}));

describe("TopNav", () => {
  it("renders all four group triggers", () => {
    render(<TopNav />);
    expect(screen.getByRole("button", { name: /Core/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Trading/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Forex/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Admin/ })).toBeInTheDocument();
  });

  it("renders the brand mark", () => {
    render(<TopNav />);
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByText(/bahtzang/)).toBeInTheDocument();
  });

  it("triggers are closed by default — no menu items visible", () => {
    render(<TopNav />);
    // Mega-menu items have role="menuitem" only when panel is open
    expect(screen.queryAllByRole("menuitem").length).toBe(0);
  });

  it("opens the Trading mega-menu on click and shows all 4 items", () => {
    render(<TopNav />);
    fireEvent.click(screen.getByRole("button", { name: /Trading/ }));
    const items = screen.getAllByRole("menuitem");
    expect(items.length).toBe(4);
    const labels = items.map((i) => i.textContent);
    expect(labels.some((t) => t?.includes("Portfolios"))).toBe(true);
    expect(labels.some((t) => t?.includes("Backtest"))).toBe(true);
    expect(labels.some((t) => t?.includes("Earnings"))).toBe(true);
    expect(labels.some((t) => t?.includes("Audit Log"))).toBe(true);
  });

  it("opens the Core mega-menu and renders descriptions for each item", () => {
    render(<TopNav />);
    fireEvent.click(screen.getByRole("button", { name: /Core/ }));
    const items = screen.getAllByRole("menuitem");
    expect(items.length).toBe(3);
    // Each item has a description child
    for (const item of items) {
      expect(item.textContent).toMatch(/.{20,}/); // label + description
    }
  });

  it("opens Forex mega-menu with single item", () => {
    render(<TopNav />);
    fireEvent.click(screen.getByRole("button", { name: /Forex/ }));
    expect(screen.getAllByRole("menuitem").length).toBe(1);
    expect(screen.getByText("Forex Backtest")).toBeInTheDocument();
  });

  it("opens Admin mega-menu with all 8 items", () => {
    render(<TopNav />);
    fireEvent.click(screen.getByRole("button", { name: /Admin/ }));
    expect(screen.getAllByRole("menuitem").length).toBe(8);
  });

  it("closes the mega-menu when Escape is pressed", () => {
    render(<TopNav />);
    fireEvent.click(screen.getByRole("button", { name: /Trading/ }));
    expect(screen.getAllByRole("menuitem").length).toBe(4);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryAllByRole("menuitem").length).toBe(0);
  });

  it("toggles the mega-menu off when the same trigger is clicked twice", () => {
    render(<TopNav />);
    const trigger = screen.getByRole("button", { name: /Trading/ });
    fireEvent.click(trigger);
    expect(screen.getAllByRole("menuitem").length).toBe(4);
    fireEvent.click(trigger);
    expect(screen.queryAllByRole("menuitem").length).toBe(0);
  });

  it("trigger has aria-expanded reflecting open state", () => {
    render(<TopNav />);
    const trigger = screen.getByRole("button", { name: /Core/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("renders search, notifications, theme toggle, and mobile button", () => {
    render(<TopNav />);
    expect(screen.getByLabelText(/Search/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Notifications/)).toBeInTheDocument();
    // Theme is "dark" in mock → toggle should switch to light mode
    expect(screen.getByLabelText(/Switch to light mode/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Open navigation menu/)).toBeInTheDocument();
  });
});
