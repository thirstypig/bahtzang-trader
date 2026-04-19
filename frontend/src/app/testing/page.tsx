const TESTS = {
  "Backend Unit Tests": {
    framework: "pytest",
    command: "npm run test:unit",
    frequency: "Every commit / pre-push",
    description:
      "Fast isolated tests that mock external dependencies. Run in ~1 second with SQLite in-memory database.",
    suites: [
      {
        file: "tests/plans/test_models.py",
        tests: 7,
        covers: "Plan, PlanTrade, PlanSnapshot model creation, serialization, defaults",
      },
      {
        file: "tests/plans/test_executor.py",
        tests: 12,
        covers: "compute_virtual_positions (buy/sell/fractional/cross-plan isolation), guardrails config generation",
      },
      {
        file: "tests/plans/test_snapshots.py",
        tests: 5,
        covers: "Daily snapshot capture, upsert behavior, inactive plan skip, position valuation",
      },
    ],
  },
  "Backend Integration Tests": {
    framework: "pytest + FastAPI TestClient",
    command: "npm run test:integration",
    frequency: "Every commit / pre-push",
    description:
      "API-level tests that hit real HTTP endpoints with SQLite. Auth is bypassed, budget validation is stubbed (pg_advisory_xact_lock is PostgreSQL-only).",
    suites: [
      {
        file: "tests/plans/test_routes.py",
        tests: 18,
        covers: "CRUD lifecycle, input validation (422), 404 handling, CSV export, target field nulling, plan snapshots endpoint",
      },
    ],
  },
  "Frontend Unit Tests": {
    framework: "Vitest + Testing Library",
    command: "npm run test:frontend",
    frequency: "Every commit / pre-push",
    description:
      "Component rendering, API client, and utility function tests. Runs in jsdom with mocked fetch and Recharts.",
    suites: [
      {
        file: "src/lib/utils.test.ts",
        tests: 6,
        covers: "formatCurrency (positive/negative/zero/large/rounding), formatDateTime, formatDate",
      },
      {
        file: "src/lib/constants.test.ts",
        tests: 3,
        covers: "GOAL_CONFIG completeness, unique labels, unique icons",
      },
      {
        file: "src/lib/api.test.ts",
        tests: 10,
        covers: "Auth headers, error handling (detail/structured/fallback), CRUD operations, runPlan timeout",
      },
      {
        file: "src/components/PlanAllocationChart.test.tsx",
        tests: 5,
        covers: "Empty state, chart rendering, total budget, percentages, legend click handler",
      },
      {
        file: "src/components/PlanPositions.test.tsx",
        tests: 7,
        covers: "Loading state, empty state, positions table, error state, positive/negative P&L rendering",
      },
    ],
  },
  "E2E Browser Tests": {
    framework: "Playwright (planned)",
    command: "npm run test:e2e",
    frequency: "Before deploys / nightly",
    description:
      "Full browser automation testing the complete user flow. Slower but catches integration bugs between frontend and backend.",
    suites: [],
  },
};

const COMMANDS = [
  { cmd: "npm test", desc: "Run all tests (backend + frontend)" },
  { cmd: "npm run test:backend", desc: "All backend tests (unit + integration)" },
  { cmd: "npm run test:frontend", desc: "All frontend tests (Vitest)" },
  { cmd: "npm run test:unit", desc: "Backend unit tests only (fastest)" },
  { cmd: "npm run test:integration", desc: "Backend API integration tests" },
  { cmd: "npm run test:backend:cov", desc: "Backend tests with coverage report" },
];

export default function TestingPage() {
  const totalTests = Object.values(TESTS).reduce(
    (sum, t) => sum + t.suites.reduce((s, suite) => s + suite.tests, 0),
    0,
  );
  const totalSuites = Object.values(TESTS).reduce(
    (sum, t) => sum + t.suites.length,
    0,
  );
  const implemented = Object.values(TESTS).filter((t) => t.suites.length > 0).length;
  const planned = Object.values(TESTS).filter((t) => t.suites.length === 0).length;

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-primary">Testing</h1>
        <p className="mt-1 text-sm text-muted">
          Test inventory, execution cadence, and coverage tracking
        </p>
      </div>

      {/* Summary cards */}
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Total Tests</p>
          <p className="mt-1 text-2xl font-bold text-primary">{totalTests}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Test Suites</p>
          <p className="mt-1 text-2xl font-bold text-primary">{totalSuites}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Categories</p>
          <p className="mt-1 text-2xl font-bold text-accent">{implemented} active</p>
          <p className="mt-0.5 text-[10px] text-muted">{planned} planned</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted">Run Time</p>
          <p className="mt-1 text-2xl font-bold text-primary">~3s</p>
          <p className="mt-0.5 text-[10px] text-muted">full suite</p>
        </div>
      </div>

      {/* Test types explained */}
      <div className="mb-8 rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Unit vs E2E Tests</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface p-4">
            <h3 className="font-semibold text-accent">Unit Tests</h3>
            <p className="mt-2 text-sm text-secondary">
              Test a single function in isolation. External dependencies (database, broker, AI) are mocked.
              Run in milliseconds. Catch logic bugs early.
            </p>
            <div className="mt-3 space-y-1 text-xs text-muted">
              <p>Speed: ~50ms each</p>
              <p>When to run: Every commit, pre-push</p>
              <p>Breaks when: Logic changes in tested function</p>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <h3 className="font-semibold text-blue-400">E2E / Integration Tests</h3>
            <p className="mt-2 text-sm text-secondary">
              Test the full system as a user would. API tests hit real endpoints. Browser tests click real buttons.
              Slower but catch integration bugs.
            </p>
            <div className="mt-3 space-y-1 text-xs text-muted">
              <p>Speed: 100ms-30s each</p>
              <p>When to run: Before deploys, nightly</p>
              <p>Breaks when: API contracts or UI change</p>
            </div>
          </div>
        </div>
      </div>

      {/* Execution cadence */}
      <div className="mb-8 rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Execution Cadence</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="px-3 py-2 text-xs font-medium text-secondary">When</th>
                <th className="px-3 py-2 text-xs font-medium text-secondary">What Runs</th>
                <th className="px-3 py-2 text-xs font-medium text-secondary">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              <tr>
                <td className="px-3 py-2 font-mono text-primary">Every commit</td>
                <td className="px-3 py-2 text-secondary">Unit + Integration tests</td>
                <td className="px-3 py-2 text-muted">~1.4s</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono text-primary">Pre-push</td>
                <td className="px-3 py-2 text-secondary">Full backend suite + TypeScript check</td>
                <td className="px-3 py-2 text-muted">~5s</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono text-primary">Before deploy</td>
                <td className="px-3 py-2 text-secondary">All tests + next build + coverage</td>
                <td className="px-3 py-2 text-muted">~30s</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono text-primary">Nightly (planned)</td>
                <td className="px-3 py-2 text-secondary">E2E browser tests</td>
                <td className="px-3 py-2 text-muted">~2min</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Commands */}
      <div className="mb-8 rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Commands</h2>
        <div className="mt-4 space-y-2">
          {COMMANDS.map((c) => (
            <div
              key={c.cmd}
              className="flex items-center justify-between rounded-lg bg-surface px-4 py-2.5"
            >
              <code className="text-sm font-semibold text-accent">{c.cmd}</code>
              <span className="text-xs text-muted">{c.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Test suites detail */}
      {Object.entries(TESTS).map(([category, info]) => (
        <div key={category} className="mb-6 rounded-xl border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-primary">{category}</h2>
              <span className="rounded bg-card-alt px-2 py-0.5 text-[10px] font-medium text-muted">
                {info.framework}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted">{info.description}</p>
            <div className="mt-2 flex items-center gap-4 text-xs text-secondary">
              <span>Frequency: {info.frequency}</span>
              <code className="text-accent">{info.command}</code>
            </div>
          </div>

          {info.suites.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm text-muted">
              Not yet implemented
            </div>
          ) : (
            <div className="divide-y divide-border/50">
              {info.suites.map((suite) => (
                <div key={suite.file} className="px-6 py-3">
                  <div className="flex items-center justify-between">
                    <code className="text-xs text-accent">{suite.file}</code>
                    <span className="rounded bg-emerald-900/30 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                      {suite.tests} tests
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted">{suite.covers}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
