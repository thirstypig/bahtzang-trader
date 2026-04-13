"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const MAIN_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/trades", label: "Trades" },
  { href: "/settings", label: "Settings" },
  { href: "/analytics", label: "Analytics" },
];

const MORE_LINKS = [
  { section: "Trading", items: [
    { href: "/roadmap", label: "Roadmap" },
    { href: "/audit-log", label: "Audit Log" },
  ]},
  { section: "Admin", items: [
    { href: "/todos", label: "To-Do List" },
    { href: "/concepts", label: "Concepts" },
    { href: "/status", label: "Status" },
    { href: "/changelog", label: "Changelog" },
    { href: "/errors", label: "Error Log" },
    { href: "/about", label: "About" },
    { href: "/docs", label: "Docs" },
  ]},
];

export default function Navbar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  function isActive(href: string) {
    return href === "/" ? pathname === "/" : pathname.startsWith(href);
  }

  const linkClass = (href: string) =>
    `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
      isActive(href)
        ? "bg-zinc-800 text-white"
        : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
    }`;

  return (
    <nav className="border-b border-zinc-800 bg-zinc-950">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
              B
            </div>
            <span className="text-lg font-semibold text-white">
              bahtzang<span className="text-emerald-400">.trader</span>
            </span>
          </Link>

          <div className="flex items-center gap-1">
            {MAIN_LINKS.map((link) => (
              <Link key={link.href} href={link.href} className={linkClass(link.href)}>
                {link.label}
              </Link>
            ))}

            {/* More dropdown */}
            <div className="relative">
              <button
                onClick={() => setMoreOpen(!moreOpen)}
                className={`flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  moreOpen
                    ? "bg-zinc-800 text-white"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
                }`}
              >
                More
                <svg
                  className={`h-3.5 w-3.5 transition-transform ${moreOpen ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {moreOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setMoreOpen(false)} />
                  <div className="absolute left-0 z-20 mt-2 w-48 rounded-xl border border-zinc-800 bg-zinc-900 py-1 shadow-xl">
                    {MORE_LINKS.map((group) => (
                      <div key={group.section}>
                        <p className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">
                          {group.section}
                        </p>
                        {group.items.map((link) => (
                          <Link
                            key={link.href}
                            href={link.href}
                            onClick={() => setMoreOpen(false)}
                            className={`block px-4 py-2 text-sm transition-colors ${
                              isActive(link.href)
                                ? "text-emerald-400"
                                : "text-zinc-400 hover:bg-zinc-800 hover:text-white"
                            }`}
                          >
                            {link.label}
                          </Link>
                        ))}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-emerald-500" title="Bot active" />
          <span className="text-xs text-zinc-500">Bot Active</span>

          {/* Profile dropdown */}
          <div className="relative">
            <button
              onClick={() => setProfileOpen(!profileOpen)}
              className="flex items-center gap-2 rounded-lg px-2 py-1 transition-colors hover:bg-zinc-800"
            >
              {user?.picture ? (
                <Image
                  src={user.picture}
                  alt={user.name || "Profile"}
                  width={32}
                  height={32}
                  className="rounded-full"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-700 text-xs font-medium text-zinc-300">
                  {user?.name
                    ?.split(" ")
                    .map((n) => n[0])
                    .join("") || "?"}
                </div>
              )}
              <svg
                className={`h-4 w-4 text-zinc-500 transition-transform ${profileOpen ? "rotate-180" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {profileOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
                <div className="absolute right-0 z-20 mt-2 w-56 rounded-xl border border-zinc-800 bg-zinc-900 py-1 shadow-xl">
                  <div className="border-b border-zinc-800 px-4 py-3">
                    <p className="text-sm font-medium text-white">{user?.name}</p>
                    <p className="text-xs text-zinc-500">{user?.email}</p>
                  </div>
                  <button
                    onClick={() => {
                      setProfileOpen(false);
                      signOut();
                    }}
                    className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                      />
                    </svg>
                    Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
