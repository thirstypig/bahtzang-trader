const TESTS = {
  "Backend Unit Tests": {
    framework: "pytest",
    command: "npm run test:unit",
    frequency: "Every commit (pre-commit hook)",
    description:
      "Fast isolated tests that mock external dependencies. Run in ~1 second with SQLite in-memory database.",
    suites: [
      {
        file: "tests/plans/test_models.py",
        tests: 7,
        covers: "Plan model creation, serialization, defaults",
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
      {
        file: "tests/plans/test_unified_trade.py",
        tests: 10,
        covers: "Unified Trade model (067-fix): global vs plan trades, to_dict conditional fields, Numeric roundtrip",
      },
      {
        file: "tests/test_analytics.py",
        tests: 20,
        covers: "Sharpe, Sortino, max drawdown, win rate, profit factor, edge cases, flat/zigzag equities",
      },
      {
        file: "tests/test_guardrails.py",
        tests: 28,
        covers: "Risk presets (conservative/moderate/aggressive), GuardrailsUpdate validation, load/save, kill switch",
      },
      {
        file: "tests/test_compliance.py",
        tests: 22,
        covers: "PDT day trade tracking, wash sale detection, avg cost calculation, 30-day window",
      },
      {
        file: "tests/test_circuit_breaker.py",
        tests: 12,
        covers: "3-tier staged halts (YELLOW/ORANGE/RED), daily/weekly loss thresholds, consecutive losses",
      },
      {
        file: "tests/test_position_sizing.py",
        tests: 10,
        covers: "Quarter-Kelly sizing, earnings proximity reduction, max position cap, negative Kelly",
      },
      {
        file: "tests/test_error_tracker.py",
        tests: 11,
        covers: "Ring buffer storage, ref lookup, eviction at capacity, error count",
      },
      {
        file: "tests/test_logger.py",
        tests: 4,
        covers: "Trade logging to DB, field persistence, None price for holds, blocked trades",
      },
    ],
  },
  "Backend Integration Tests": {
    framework: "pytest + FastAPI TestClient",
    command: "npm run test:integration",
    frequency: "Every commit (pre-commit hook)",
    description:
      "API-level tests that hit real HTTP endpoints with SQLite. Auth is bypassed, budget validation is stubbed (pg_advisory_xact_lock is PostgreSQL-only).",
    suites: [
      {
        file: "tests/plans/test_routes.py",
        tests: 18,
        covers: "Plan CRUD lifecycle, input validation (422), 404 handling, CSV export, target field nulling, snapshots",
      },
      {
        file: "tests/earnings/test_routes.py",
        tests: 6,
        covers: "Earnings calendar GET, symbol lookup, day bounds validation, refresh error sanitization",
      },
      {
        file: "tests/test_trades_routes.py",
        tests: 3,
        covers: "/trades includes plan trades (067-fix), /trades/export includes plan trades for tax",
      },
      {
        file: "tests/test_guardrails_routes.py",
        tests: 10,
        covers: "Config CRUD, risk presets, kill switch activate/deactivate with audit trail",
      },
      {
        file: "tests/test_portfolio_routes.py",
        tests: 5,
        covers: "Snapshots, metrics with Decimal data, insufficient data handling, /health",
      },
      {
        file: "tests/test_bot_routes.py",
        tests: 7,
        covers: "Bot status, executed trade count, last run, /trades/summary, full plan lifecycle E2E",
      },
      {
        file: "tests/test_backtest_routes.py",
        tests: 13,
        covers: "Strategies list, backtest CRUD, pending status, config retrieval, delete, validation",
      },
      {
        file: "tests/test_todos_routes.py",
        tests: 16,
        covers: "Todo CRUD with JSON persistence isolation, status filter, validation, 422/404 handling",
      },
    ],
  },
  "Frontend Unit Tests": {
    framework: "Vitest + Testing Library",
    command: "npm run test:frontend",
    frequency: "Every commit (pre-commit hook)",
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
        file: "src/lib/useApiQuery.test.ts",
        tests: 5,
        covers: "Loading/data/error states, no-fetch when no user, refetch on dependency change",
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
      {
        file: "src/components/TradeTable.test.tsx",
        tests: 11,
        covers: "Table rendering, Passed/Blocked badges, BUY/SELL/HOLD colors, confidence %, sorting",
      },
      {
        file: "src/components/ConfirmModal.test.tsx",
        tests: 7,
        covers: "Open/close, title/message, confirm/cancel callbacks, custom labels, backdrop click",
      },
      {
        file: "src/components/KillSwitchButton.test.tsx",
        tests: 7,
        covers: "Activate/deactivate states, API calls, loading states, cancel without API call",
      },
      {
        file: "src/components/Sidebar.test.tsx",
        tests: 6,
        covers: "Nav groups (Core/Trading/Admin), all 16 links, active state, brand logo, theme toggle",
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
  { cmd: "npm run test:backend", desc: "All backend tests (229 tests)" },
  { cmd: "npm run test:frontend", desc: "All frontend tests (68 tests)" },
  { cmd: "npm run test:unit", desc: "Backend unit tests only (fastest)" },
  { cmd: "npm run test:integration", desc: "Backend API integration tests" },
  { cmd: "npm run test:backend:cov", desc: "Backend tests with coverage report" },
  { cmd: "npm run test:coverage", desc: "Frontend tests with coverage report" },
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
          <p className="mt-1 text-2xl font-bold text-primary">~5s</p>
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
              <p>When to run: Every commit (pre-commit hook)</p>
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
              <p>When to run: Every commit + CI on push</p>
              <p>Breaks when: API contracts or UI change</p>
            </div>
          </div>
        </div>
      </div>

      {/* Automation */}
      <div className="mb-8 rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Automation</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="px-3 py-2 text-xs font-medium text-secondary">Layer</th>
                <th className="px-3 py-2 text-xs font-medium text-secondary">What Runs</th>
                <th className="px-3 py-2 text-xs font-medium text-secondary">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              <tr>
                <td className="px-3 py-2 font-mono text-accent">Pre-commit hook</td>
                <td className="px-3 py-2 text-secondary">tsc + pytest (229) + vitest (68)</td>
                <td className="px-3 py-2 text-muted">Every git commit (~5s)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono text-accent">GitHub Actions CI</td>
                <td className="px-3 py-2 text-secondary">Backend job + Frontend job (parallel)</td>
                <td className="px-3 py-2 text-muted">Every push / PR to main</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono text-accent">Coverage reports</td>
                <td className="px-3 py-2 text-secondary">pytest-cov + vitest v8 provider</td>
                <td className="px-3 py-2 text-muted">On demand (npm run test:*:cov)</td>
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
