const DOCS = [
  {
    category: "Getting Started",
    items: [
      {
        title: "README",
        description: "Project overview, setup, and development instructions",
        href: "https://github.com/thirstypig/bahtzang-trader#readme",
        icon: "📖",
      },
      {
        title: "CLAUDE.md",
        description: "Project conventions, architecture, patterns, and deployment notes for Claude Code",
        href: "https://github.com/thirstypig/bahtzang-trader/blob/main/CLAUDE.md",
        icon: "🤖",
      },
      {
        title: "Environment Variables",
        description: "All required env vars for backend and frontend",
        href: "https://github.com/thirstypig/bahtzang-trader/blob/main/backend/.env.example",
        icon: "🔑",
      },
    ],
  },
  {
    category: "Architecture",
    items: [
      {
        title: "Roadmap & Architecture Plan",
        description: "Deepened plan with multi-broker strategy, risk management, and 12-page structure",
        href: "https://github.com/thirstypig/bahtzang-trader/blob/main/docs/plans/2026-04-10-bahtzang-trader-roadmap-deepened.md",
        icon: "🗺️",
      },
      {
        title: "Port Assignments",
        description: "Local development ports (frontend: 3060, API: 4060)",
        href: "https://github.com/thirstypig/bahtzang-trader/blob/main/ports.md",
        icon: "🔌",
      },
    ],
  },
  {
    category: "API Reference",
    items: [
      {
        title: "Swagger UI (Backend API)",
        description: "Interactive API documentation — all endpoints with try-it-out",
        href: "https://bahtzang-backend-production.up.railway.app/docs",
        icon: "⚡",
      },
      {
        title: "Health Check",
        description: "GET /health — verify the backend is running",
        href: "https://bahtzang-backend-production.up.railway.app/health",
        icon: "💚",
      },
    ],
  },
  {
    category: "Infrastructure",
    items: [
      {
        title: "Railway Dashboard",
        description: "Manage deployments, env vars, and service logs",
        href: "https://railway.app/dashboard",
        icon: "🚂",
      },
      {
        title: "Supabase Dashboard",
        description: "Database, auth, and API key management",
        href: "https://supabase.com/dashboard",
        icon: "⚙️",
      },
      {
        title: "GitHub Repository",
        description: "Source code, issues, and pull requests",
        href: "https://github.com/thirstypig/bahtzang-trader",
        icon: "🐙",
      },
    ],
  },
];

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-primary">Documentation</h1>
        <p className="mt-1 text-sm text-muted">
          Guides, references, and infrastructure links
        </p>
      </div>

      <div className="space-y-8">
        {DOCS.map((section) => (
          <div key={section.category}>
            <h2 className="mb-3 text-sm font-semibold text-accent">
              {section.category}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {section.items.map((item) => (
                <a
                  key={item.title}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group rounded-xl border border-border bg-card p-5 transition-colors hover:border-border-strong hover:bg-card-alt/50"
                >
                  <div className="flex items-start gap-3">
                    <span className="text-lg">{item.icon}</span>
                    <div>
                      <h3 className="text-sm font-medium text-primary group-hover:text-accent">
                        {item.title}
                      </h3>
                      <p className="mt-1 text-xs text-muted">
                        {item.description}
                      </p>
                    </div>
                  </div>
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
