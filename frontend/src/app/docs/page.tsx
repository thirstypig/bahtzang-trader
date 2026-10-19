"use client";

import { useEffect, useState } from "react";
import Spinner from "@/components/Spinner";
import { renderMarkdown } from "@/lib/renderMarkdown";

interface DocEntry {
  id: string;
  title: string;
  description: string;
  icon: string;
  file: string | null;
  href?: string;
}

const DOCS: { category: string; items: DocEntry[] }[] = [
  {
    category: "Getting Started",
    items: [
      { id: "daily-ops", title: "Daily Operations Guide", description: "What to check daily, how to use each page, getting started checklist", icon: "📋", file: "/docs/daily-operations.md" },
      { id: "feature-inventory", title: "Feature Inventory", description: "Every feature in plain English — and whether it actually affects trades today", icon: "🔎", file: "/docs/feature-inventory.md" },
    ],
  },
  {
    category: "Project Docs",
    items: [
      { id: "readme", title: "README", description: "Project overview, setup, and development", icon: "📖", file: "/docs/readme.md" },
      { id: "claude", title: "CLAUDE.md", description: "Architecture, conventions, and patterns", icon: "🤖", file: "/docs/claude.md" },
      { id: "ports", title: "Port Assignments", description: "Local dev ports (frontend: 3070, API: 4070)", icon: "🔌", file: "/docs/ports.md" },
    ],
  },
  {
    category: "Plans",
    items: [
      { id: "investment-plans", title: "Investment Plans", description: "Pie-style portfolio slices — deepened architecture plan", icon: "🥧", file: "/docs/investment-plans.md" },
      { id: "trading-frequency", title: "Trading Frequency & Goals", description: "Trading goals, frequency scheduling, and APScheduler integration", icon: "📊", file: "/docs/trading-frequency-goals.md" },
      { id: "admin-system", title: "Admin System", description: "Todo CRUD, roadmap, concepts, changelog — full admin feature plan", icon: "🛠️", file: "/docs/admin-system-plan.md" },
    ],
  },
  {
    category: "External Links",
    items: [
      { id: "swagger", title: "API Docs (Swagger)", description: "Interactive API — all endpoints with try-it-out", icon: "⚡", file: null, href: "https://bahtzang-backend-production.up.railway.app/docs" },
      { id: "railway", title: "Railway Dashboard", description: "Deployments, env vars, and service logs", icon: "🚂", file: null, href: "https://railway.app/dashboard" },
      { id: "supabase", title: "Supabase Dashboard", description: "Database, auth, and API keys", icon: "⚙️", file: null, href: "https://supabase.com/dashboard" },
      { id: "github", title: "GitHub Repository", description: "Source code, issues, and pull requests", icon: "🐙", file: null, href: "https://github.com/thirstypig/bahtzang-trader" },
    ],
  },
];

export default function DocsPage() {
  const [activeDoc, setActiveDoc] = useState<DocEntry>(DOCS[0].items[0]); // Daily Operations Guide
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!activeDoc.file) return;
    setLoading(true);
    fetch(activeDoc.file)
      .then((res) => res.ok ? res.text() : "Failed to load document.")
      .then((text) => {
        setContent(text);
        setLoading(false);
      })
      .catch(() => {
        setContent("Failed to load document.");
        setLoading(false);
      });
  }, [activeDoc]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-primary">Documentation</h1>
        <p className="mt-1 text-sm text-muted">
          Guides, references, and architecture docs — read them right here
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* Sidebar — doc list */}
        <div className="space-y-6">
          {DOCS.map((section) => (
            <div key={section.category}>
              <h2 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted">
                {section.category}
              </h2>
              <div className="space-y-1">
                {section.items.map((item) =>
                  item.file ? (
                    <button
                      key={item.id}
                      onClick={() => setActiveDoc(item)}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                        activeDoc.id === item.id
                          ? "bg-accent/10 text-accent"
                          : "text-secondary hover:bg-card-alt hover:text-primary"
                      }`}
                    >
                      <span>{item.icon}</span>
                      <div className="min-w-0">
                        <p className="font-medium">{item.title}</p>
                        <p className="truncate text-[10px] text-muted">{item.description}</p>
                      </div>
                    </button>
                  ) : (
                    <a
                      key={item.id}
                      href={item.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-secondary transition-colors hover:bg-card-alt hover:text-primary"
                    >
                      <span>{item.icon}</span>
                      <div className="min-w-0">
                        <p className="font-medium">{item.title}</p>
                        <p className="truncate text-[10px] text-muted">{item.description}</p>
                      </div>
                      <svg className="ml-auto h-3 w-3 shrink-0 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-4.5-4.5h6m0 0v6m0-6L10.5 13.5" />
                      </svg>
                    </a>
                  )
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Content panel */}
        <div className="bz-glass p-6 lg:p-8">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Spinner />
            </div>
          ) : (
            <article
              className="prose-custom"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
