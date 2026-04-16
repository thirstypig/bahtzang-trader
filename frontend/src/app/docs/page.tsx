"use client";

import { useEffect, useState } from "react";
import Spinner from "@/components/Spinner";

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
    category: "Project Docs",
    items: [
      { id: "readme", title: "README", description: "Project overview, setup, and development", icon: "📖", file: "/docs/readme.md" },
      { id: "claude", title: "CLAUDE.md", description: "Architecture, conventions, and patterns", icon: "🤖", file: "/docs/claude.md" },
      { id: "ports", title: "Port Assignments", description: "Local dev ports (frontend: 3060, API: 4060)", icon: "🔌", file: "/docs/ports.md" },
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

function renderMarkdown(md: string): string {
  let html = md
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="rounded-lg bg-card-alt p-4 overflow-x-auto text-xs font-mono text-secondary my-3"><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="rounded bg-card-alt px-1.5 py-0.5 text-xs font-mono text-accent">$1</code>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="mt-6 mb-2 text-base font-semibold text-primary">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="mt-8 mb-3 text-lg font-bold text-primary border-b border-border pb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="mt-8 mb-4 text-xl font-bold text-primary">$1</h1>')
    // Bold and italic
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-primary">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-accent underline hover:text-accent-text">$1</a>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-secondary">$1</li>')
    // Horizontal rules
    .replace(/^---$/gm, '<hr class="my-6 border-border" />')
    // Paragraphs (lines not already wrapped)
    .replace(/^(?!<[hluop]|<li|<hr|<pre|<code)(.+)$/gm, '<p class="my-2 text-secondary leading-relaxed">$1</p>');

  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li[^>]*>.*<\/li>\n?)+)/g, '<ul class="my-3 space-y-1">$1</ul>');

  return html;
}

export default function DocsPage() {
  const [activeDoc, setActiveDoc] = useState<DocEntry>(DOCS[0].items[0]);
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
        <div className="rounded-xl border border-border bg-card p-6 lg:p-8">
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
