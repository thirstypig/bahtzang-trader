import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Sidebar from "./Sidebar";

// Mock Next.js navigation
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

// Mock sidebar context
vi.mock("@/lib/sidebar", () => ({
  useSidebar: () => ({ expanded: true, mobile: false, toggle: vi.fn() }),
}));

// Mock ThemeToggle and SidebarProfile
vi.mock("@/components/ThemeToggle", () => ({
  default: () => <div data-testid="theme-toggle" />,
}));
vi.mock("@/components/SidebarProfile", () => ({
  default: () => <div data-testid="sidebar-profile" />,
}));

describe("Sidebar", () => {
  it("renders all nav groups", () => {
    render(<Sidebar />);
    expect(screen.getByText("Core")).toBeInTheDocument();
    expect(screen.getByText("Trading")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("renders all navigation links", () => {
    render(<Sidebar />);
    const expectedLabels = [
      "Dashboard", "Trades", "Analytics",
      "Settings", "Backtest", "Earnings", "Plans", "Audit Log",
      "Todos", "Roadmap", "Status", "Errors", "Changelog",
      "About", "Testing", "Docs",
    ];
    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders correct number of links (16 pages)", () => {
    render(<Sidebar />);
    const links = screen.getAllByRole("link");
    // 16 nav links + 1 logo link = 17
    expect(links.length).toBe(17);
  });

  it("marks Dashboard as active on root path", () => {
    render(<Sidebar />);
    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink).toHaveAttribute("aria-current", "page");
  });

  it("renders brand logo", () => {
    render(<Sidebar />);
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByText(/bahtzang/)).toBeInTheDocument();
  });

  it("renders theme toggle and profile", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("theme-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-profile")).toBeInTheDocument();
  });
});
