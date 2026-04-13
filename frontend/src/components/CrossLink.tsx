"use client";

import Link from "next/link";

type LinkTarget = "roadmap" | "todo" | "changelog" | "concept";

const LINK_STYLES: Record<LinkTarget, { bg: string; text: string; label: string }> = {
  roadmap: { bg: "bg-purple-900/30", text: "text-purple-400", label: "Roadmap" },
  todo: { bg: "bg-zinc-800", text: "text-zinc-400", label: "Todo" },
  changelog: { bg: "bg-blue-900/30", text: "text-blue-400", label: "Changelog" },
  concept: { bg: "bg-amber-900/30", text: "text-amber-400", label: "Concept" },
};

interface CrossLinkProps {
  type: LinkTarget;
  href: string;
  label?: string;
}

export default function CrossLink({ type, href, label }: CrossLinkProps) {
  const style = LINK_STYLES[type];

  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors hover:brightness-125 ${style.bg} ${style.text}`}
    >
      <svg
        className="h-2.5 w-2.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-4.5-4.5h6m0 0v6m0-6L10.5 13.5"
        />
      </svg>
      {label || style.label}
    </Link>
  );
}
