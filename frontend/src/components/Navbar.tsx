"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/trades", label: "Trades" },
  { href: "/settings", label: "Settings" },
];

export default function Navbar() {
  const pathname = usePathname();

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

          <div className="flex gap-1">
            {NAV_LINKS.map((link) => {
              const isActive =
                link.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-zinc-800 text-white"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-emerald-500" title="Bot active" />
          <span className="text-xs text-zinc-500">Bot Active</span>
          <div className="h-8 w-8 overflow-hidden rounded-full bg-zinc-700">
            {/* Google profile photo — src set dynamically after OAuth */}
            <div className="flex h-full w-full items-center justify-center text-xs font-medium text-zinc-300">
              JC
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
