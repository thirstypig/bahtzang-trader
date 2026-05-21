"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import * as Icons from "@/components/icons";

/* ── Navigation structure ──────────────────────────────────
   Source of truth: the original Sidebar.tsx NAV groups.
   Pages and groups must not be invented here — only the
   1-line descriptions are added (for the mega-menu).
   ────────────────────────────────────────────────────────── */

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  description: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    title: "Core",
    items: [
      { href: "/", label: "Portfolio", icon: Icons.Dashboard, description: "Your holdings, total value, and latest AI decision" },
      { href: "/trades", label: "Trades", icon: Icons.Trades, description: "Full trade history with reasoning" },
      { href: "/analytics", label: "Analytics", icon: Icons.Analytics, description: "Sharpe, drawdown, win-rate, equity curve" },
    ],
  },
  {
    title: "Trading",
    items: [
      { href: "/portfolios", label: "Strategies", icon: Icons.Plans, description: "Each strategy's budget, rules, and kill switch" },
      { href: "/screener", label: "Screener", icon: Icons.Analytics, description: "Daily ranked S&P 500 candidates (advisory)" },
      { href: "/markets", label: "Markets", icon: Icons.Markets, description: "Financial products: current, near-term, and future" },
      { href: "/backtest", label: "Backtest", icon: Icons.Backtest, description: "Stocks strategy backtests on historical data" },
      { href: "/earnings", label: "Earnings", icon: Icons.Earnings, description: "Upcoming earnings with proximity warnings" },
      { href: "/audit-log", label: "Audit Log", icon: Icons.AuditLog, description: "Per-portfolio strategy change history" },
    ],
  },
  {
    title: "Forex",
    items: [
      { href: "/forex", label: "Forex Backtest", icon: Icons.Forex, description: "Independent swing-zone strategy backtester" },
    ],
  },
  {
    title: "Admin",
    items: [
      { href: "/todos", label: "Todos", icon: Icons.Todos, description: "Tasks tracked across the project" },
      { href: "/roadmap", label: "Roadmap", icon: Icons.Roadmap, description: "Phased plan + status of in-flight work" },
      { href: "/status", label: "Status", icon: Icons.Status, description: "Live system health checks" },
      { href: "/errors", label: "Errors", icon: Icons.Errors, description: "Recent backend errors with context" },
      { href: "/changelog", label: "Changelog", icon: Icons.Changelog, description: "Notable releases and fixes" },
      { href: "/about", label: "About", icon: Icons.About, description: "What this is and who it's for" },
      { href: "/testing", label: "Testing", icon: Icons.Testing, description: "Test inventory and execution cadence" },
      { href: "/docs", label: "Docs", icon: Icons.Docs, description: "Architecture and how-to references" },
      { href: "/settings", label: "Settings", icon: Icons.Settings, description: "Timezone, display preferences, defaults" },
    ],
  },
];

/* ── Reusable item-card (used by both desktop mega-menu + mobile sheet) ── */

interface NavItemCardProps {
  item: NavItem;
  active: boolean;
  role?: "menuitem";
}

function NavItemCard({ item, active, role }: NavItemCardProps) {
  return (
    <Link
      href={item.href}
      role={role}
      aria-current={active ? "page" : undefined}
      className={`group flex items-start gap-3 rounded-xl p-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
        active ? "bg-accent/15 ring-1 ring-accent/30" : "hover:bg-accent/8"
      }`}
    >
      <span className={`mt-0.5 ${active ? "text-accent" : "text-muted group-hover:text-secondary"}`}>
        {item.icon}
      </span>
      <span className="min-w-0">
        <span className={`block text-sm font-medium ${active ? "text-accent" : "text-primary"}`}>
          {item.label}
        </span>
        <span className="block text-xs text-muted">{item.description}</span>
      </span>
    </Link>
  );
}

/* ── Component ─────────────────────────────────────────── */

export default function TopNav() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const { user, signOut } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!profileOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [profileOpen]);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);

  // Close on route change.
  useEffect(() => {
    setOpenGroup(null);
    setMobileOpen(false);
  }, [pathname]);

  // Close on outside click.
  useEffect(() => {
    if (!openGroup) return;
    function handler(e: MouseEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setOpenGroup(null);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [openGroup]);

  // Close on Esc.
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpenGroup(null);
        setMobileOpen(false);
      }
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  function isActive(href: string) {
    return href === "/"
      ? pathname === "/"
      : pathname === href || pathname.startsWith(href + "/");
  }

  function isActiveGroup(group: NavGroup) {
    return group.items.some((item) => isActive(item.href));
  }

  const currentGroup = openGroup ? NAV.find((g) => g.title === openGroup) ?? null : null;

  return (
    <>
      <nav
        ref={navRef}
        aria-label="Primary"
        className="bz-glass-strong fixed inset-x-0 top-0 z-40 h-14 !rounded-none"
      >
        <div className="mx-auto flex h-full max-w-7xl items-center justify-between gap-4 px-4">
          {/* ── Brand ── */}
          <Link
            href="/"
            className="flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white shadow-sm">
              B
            </div>
            <span className="hidden whitespace-nowrap text-sm font-semibold text-primary sm:inline">
              bahtzang<span className="bz-gradient-text">.trader</span>
            </span>
          </Link>

          {/* ── Group triggers (desktop ≥lg) ── */}
          <ul className="hidden items-center gap-1 lg:flex">
            {NAV.map((group) => {
              const open = openGroup === group.title;
              const active = isActiveGroup(group);
              return (
                <li key={group.title}>
                  <button
                    type="button"
                    aria-haspopup="true"
                    aria-expanded={open}
                    aria-controls={`mega-menu-${group.title}`}
                    onClick={() => setOpenGroup(open ? null : group.title)}
                    onMouseEnter={() => setOpenGroup(group.title)}
                    onFocus={() => setOpenGroup(group.title)}
                    className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                      active ? "text-primary" : "text-secondary hover:text-primary"
                    }`}
                  >
                    {group.title}
                    <svg
                      className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                    </svg>
                  </button>
                </li>
              );
            })}
          </ul>

          {/* ── Right cluster: search, notifications, theme, avatar, mobile ── */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Search (⌘K)"
              title="Search (⌘K)"
              className="hidden items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:flex"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <kbd className="hidden rounded border border-border-strong/40 px-1 py-0.5 font-mono text-[10px] xl:inline">⌘K</kbd>
            </button>

            <button
              type="button"
              aria-label="Notifications"
              className="rounded-md p-1.5 text-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
            </button>

            <button
              type="button"
              onClick={toggle}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              title={theme === "dark" ? "Light mode" : "Dark mode"}
              className="rounded-md p-1.5 text-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              {theme === "dark" ? (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
                </svg>
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
                </svg>
              )}
            </button>

            <div ref={profileRef} className="relative hidden sm:block">
              <button
                type="button"
                onClick={() => setProfileOpen((v) => !v)}
                aria-label="Account menu"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/30 text-xs font-semibold text-primary hover:bg-accent/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                {user?.name ? user.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase() : "JC"}
              </button>
              {profileOpen && (
                <div className="absolute right-0 top-full mt-2 w-52 bz-glass-strong rounded-xl shadow-lg py-1 z-50">
                  {user?.email && (
                    <div className="px-4 py-2 border-b border-border">
                      <p className="text-xs text-muted truncate">{user.email}</p>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => { setProfileOpen(false); signOut(); }}
                    className="w-full text-left px-4 py-2 text-sm text-neg hover:bg-neg/10 transition-colors"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={mobileOpen}
              className="rounded-md p-1.5 text-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent lg:hidden"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            </button>
          </div>
        </div>

        {/* ── Mega-menu panel (desktop) ── */}
        {currentGroup && (
          <div
            id={`mega-menu-${currentGroup.title}`}
            role="menu"
            onMouseLeave={() => setOpenGroup(null)}
            className="bz-glass-strong absolute inset-x-0 top-full mx-auto mt-2 max-w-7xl !rounded-2xl"
          >
            <div className="grid grid-cols-1 gap-1 p-3 sm:grid-cols-2 lg:grid-cols-3">
              {currentGroup.items.map((item) => (
                <NavItemCard
                  key={item.href}
                  item={item}
                  active={isActive(item.href)}
                  role="menuitem"
                />
              ))}
            </div>
          </div>
        )}
      </nav>

      {/* ── Mobile sheet ── */}
      {mobileOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            className="bz-glass-strong fixed inset-x-0 bottom-0 top-14 z-50 overflow-y-auto !rounded-none lg:hidden"
          >
            <div className="mx-auto max-w-3xl space-y-6 p-4">
              {NAV.map((group) => (
                <div key={group.title}>
                  <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-widest text-muted">
                    {group.title}
                  </p>
                  <ul className="grid grid-cols-1 gap-1">
                    {group.items.map((item) => (
                      <li key={item.href}>
                        <NavItemCard item={item} active={isActive(item.href)} />
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
