"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSidebar } from "@/lib/sidebar";
import ThemeToggle from "@/components/ThemeToggle";
import SidebarProfile from "@/components/SidebarProfile";
import * as Icons from "@/components/icons";

/* ── Navigation structure ────────────────────────────── */

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    title: "Core",
    items: [
      { href: "/", label: "Dashboard", icon: Icons.Dashboard },
      { href: "/trades", label: "Trades", icon: Icons.Trades },
      { href: "/analytics", label: "Analytics", icon: Icons.Analytics },
    ],
  },
  {
    title: "Trading",
    items: [
      { href: "/settings", label: "Settings", icon: Icons.Settings },
      { href: "/backtest", label: "Backtest", icon: Icons.Backtest },
      { href: "/earnings", label: "Earnings", icon: Icons.Earnings },
      { href: "/plans", label: "Plans", icon: Icons.Plans },
      { href: "/audit-log", label: "Audit Log", icon: Icons.AuditLog },
    ],
  },
  {
    title: "Admin",
    items: [
      { href: "/todos", label: "Todos", icon: Icons.Todos },
      { href: "/roadmap", label: "Roadmap", icon: Icons.Roadmap },
      { href: "/status", label: "Status", icon: Icons.Status },
      { href: "/errors", label: "Errors", icon: Icons.Errors },
      { href: "/changelog", label: "Changelog", icon: Icons.Changelog },
      { href: "/about", label: "About", icon: Icons.About },
      { href: "/docs", label: "Docs", icon: Icons.Docs },
    ],
  },
];

/* ── Sidebar component ───────────────────────────────── */

export default function Sidebar() {
  const pathname = usePathname();
  const { expanded, mobile, toggle: toggleSidebar } = useSidebar();

  function isActive(href: string) {
    return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <>
      {/* Mobile backdrop */}
      {mobile && expanded && (
        <div
          className="fixed inset-0 z-20 bg-black/50 transition-opacity"
          onClick={toggleSidebar}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-card transition-all duration-200 ${
          mobile
            ? expanded ? "w-60 translate-x-0" : "w-60 -translate-x-full"
            : expanded ? "w-60" : "w-[68px]"
        }`}
      >
      {/* ── Logo + collapse toggle ── */}
      <div className="flex h-14 items-center justify-between border-b border-border px-4">
        <Link href="/" className="flex items-center gap-2.5 overflow-hidden">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
            B
          </div>
          {expanded && (
            <span className="whitespace-nowrap text-sm font-semibold text-primary">
              bahtzang<span className="text-accent">.trader</span>
            </span>
          )}
        </Link>
        <button
          onClick={toggleSidebar}
          className="rounded-md p-1 text-muted transition-colors hover:bg-card-alt hover:text-secondary"
          title={expanded ? "Collapse" : "Expand"}
        >
          <svg className={`h-4 w-4 transition-transform ${expanded ? "" : "rotate-180"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV.map((group) => (
          <div key={group.title} className="mb-5">
            {expanded && (
              <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted">
                {group.title}
              </p>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      title={expanded ? undefined : item.label}
                      className={`group flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
                        active
                          ? "bg-accent/10 text-accent"
                          : "text-secondary hover:bg-card-alt hover:text-primary"
                      }`}
                    >
                      <span className={active ? "text-accent" : "text-muted group-hover:text-secondary"}>
                        {item.icon}
                      </span>
                      {expanded && <span>{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* ── Footer: theme toggle + profile ── */}
      <div className="border-t border-border p-3">
        <div className="mb-2">
          <ThemeToggle expanded={expanded} />
        </div>
        <SidebarProfile expanded={expanded} />
      </div>
    </aside>
    </>
  );
}
