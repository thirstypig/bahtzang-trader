"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ADMIN_LINKS = [
  { href: "/todos", label: "Todo" },
  { href: "/roadmap", label: "Roadmap" },
  { href: "/concepts", label: "Concepts" },
  { href: "/changelog", label: "Changelog" },
];

export default function AdminNav() {
  const pathname = usePathname();

  return (
    <nav
      className="mb-6 flex items-center gap-1 border-b border-zinc-800 pb-3"
      aria-label="Admin pages"
    >
      {ADMIN_LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            pathname === link.href
              ? "bg-zinc-800 text-white"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
