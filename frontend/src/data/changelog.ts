export interface ChangelogEntry {
  version: string;
  date: string;
  changes: {
    type: "feat" | "fix" | "docs" | "perf" | "refactor";
    title: string;
  }[];
}

export const changelog: ChangelogEntry[] = [
  {
    version: "0.4.0",
    date: "2026-04-10",
    changes: [
      { type: "feat", title: "Admin pages: roadmap, changelog, about, status, docs, audit log" },
      { type: "feat", title: "Updated navigation with grouped page structure" },
      { type: "feat", title: "Deepened roadmap plan with multi-broker architecture" },
    ],
  },
  {
    version: "0.3.0",
    date: "2026-04-09",
    changes: [
      { type: "feat", title: "Migrate auth and database to Supabase" },
      { type: "fix", title: "JWT verification: ES256 via JWKS endpoint (not legacy HS256)" },
      { type: "fix", title: "Token injection from AuthProvider to API layer" },
      { type: "fix", title: "Graceful error handling when Schwab API unavailable" },
    ],
  },
  {
    version: "0.2.0",
    date: "2026-04-08",
    changes: [
      { type: "feat", title: "Google OAuth authentication with JWT sessions" },
      { type: "feat", title: "Login page with Google Sign-In" },
      { type: "feat", title: "Navbar with profile photo and sign-out" },
      { type: "feat", title: "Route protection — redirect to /login when unauthenticated" },
    ],
  },
  {
    version: "0.1.0",
    date: "2026-04-08",
    changes: [
      { type: "feat", title: "Next.js 14 dashboard with dark theme and Recharts" },
      { type: "feat", title: "FastAPI backend with Claude AI decision engine" },
      { type: "feat", title: "Schwab API client for portfolio and order management" },
      { type: "feat", title: "Alpha Vantage market data and news integration" },
      { type: "feat", title: "Guardrails system with kill switch" },
      { type: "feat", title: "APScheduler cron at 9:35 AM ET on market days" },
      { type: "feat", title: "Railway deployment configuration" },
    ],
  },
];
