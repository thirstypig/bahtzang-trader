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
        file: "tests/plans/test_constraints.py",
        tests: 11,
        covers: "Cooldown enforcement, frequency cap (buy/sell), repeat-action guard, cross-portfolio isolation, touch history upsert",
      },
      {
        file: "tests/plans/test_executor.py",
        tests: 13,
        covers: "compute_virtual_positions (buy/sell/fractional/cross-portfolio isolation), float type invariant (Decimal+float production crash), usage stats passed to Claude prompt",
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
        tests: 22,
        covers: "Sharpe, Sortino, max drawdown, win rate, profit factor, edge cases, flat/zigzag equities",
      },
      {
        file: "tests/test_default_portfolio.py",
        tests: 2,
        covers: "Default portfolio creation on empty table, idempotent when portfolio already exists",
      },
      {
        file: "tests/test_compliance.py",
        tests: 22,
        covers: "PDT day trade tracking, wash sale detection, avg cost calculation, 30-day window",
      },
      {
        file: "tests/test_circuit_breaker.py",
        tests: 14,
        covers: "3-tier staged halts (YELLOW/ORANGE/RED), daily/weekly loss thresholds, consecutive losses",
      },
      {
        file: "tests/test_position_sizing.py",
        tests: 10,
        covers: "Quarter-Kelly sizing, earnings proximity reduction, max position cap, negative Kelly",
      },
      {
        file: "tests/test_error_tracker.py",
        tests: 10,
        covers: "Ring buffer storage, ref lookup, eviction at capacity, error count",
      },
      {
        file: "tests/test_logger.py",
        tests: 4,
        covers: "Trade logging to DB, field persistence, None price for holds, blocked trades",
      },
      {
        file: "tests/test_claude_brain_prompt.py",
        tests: 15,
        covers: "Headroom block (invested, orders, position slots, effective buy ceiling, sizing, backward-compat) + timeline-goal sanitization (valid render, malformed date suppressed, uncoercible amount suppressed, zero/negative suppressed, string-numeric coerced) + exit-only block (present when flagged with stop-loss %, absent by default) + screener CSV block (rendered with weighting note when fed, absent by default)",
      },
      {
        file: "tests/test_claude_brain_review.py",
        tests: 5,
        covers: "review_trade_decision() oversight function: normal confirm, earnings override, malformed JSON fail-closed, APITimeoutError fail-closed, kill switch context",
      },
      {
        file: "tests/test_dual_momentum_strategy.py",
        tests: 12,
        covers: "Antonacci Dual Momentum: SPY vs VEU comparison, BIL rotation when both negative, 1-month/12-month lookbacks, insufficient data handling, parameter overrides",
      },
      {
        file: "tests/test_goal_prompts.py",
        tests: 7,
        covers: "GOAL_PROMPTS/GOAL_WATCHLIST safety: no bare crypto in any prompt or watchlist, expected goal keys present, all watchlist tickers are plain 1-5 letter symbols (no dotted/class-share tickers), regression guard against BTC/ETH re-introduction",
      },
      {
        file: "tests/test_market_data.py",
        tests: 3,
        covers: "get_quotes partial-failure hardening: one ticker raising is dropped (batch survives), all-fail returns [] not an exception, happy-path passthrough",
      },
      {
        file: "tests/screener/test_engine.py",
        tests: 9,
        covers: "Screener rank_universe (pure): uptrend outranks downtrend, insufficient-history excluded, extreme-volatility excluded, top_n cap + rank numbering, empty universe; _compute_factors None below min bars + trend score; $20M liquidity floor (thin names excluded, liquid pass)",
      },
      {
        file: "tests/test_zero_qty_coercion.py",
        tests: 13,
        covers: "Coerce buy/sell with qty<=0 or price<=0 to hold before validation; plan executor passes total_invested + orders_today to Claude prompt",
      },
      {
        file: "tests/test_crypto_support.py",
        tests: 9,
        covers: "Crypto routing: is_crypto slash-pair classification; indicators route crypto to CryptoHistoricalDataClient (stock client never sees pairs, one client's failure doesn't blank the other); orders use GTC for crypto / DAY for equities; AV quotes+news never see slash pairs while Alpaca indicators do (price source)",
      },
      {
        file: "tests/test_allowed_emails.py",
        tests: 7,
        covers: "ALLOWED_EMAIL CSV parser: single/multi, whitespace, case-insensitive, empty segments, NFKC full-width normalization, Cyrillic homoglyph rejection",
      },
      {
        file: "tests/forex/test_zones.py",
        tests: 7,
        covers: "Pivot detection (5-bar, strict <), single-linkage clustering (0.5%), zone construction",
      },
      {
        file: "tests/forex/test_patterns.py",
        tests: 10,
        covers: "Bullish/bearish pin bar (2× wick / 0.5× opposing), body-engulfing, doji rejection",
      },
      {
        file: "tests/forex/test_engine.py",
        tests: 8,
        covers: "quote_to_usd USD-quote/base, bracket exit precedence (SL > TP > zone-break), synthetic E2E",
      },
      {
        file: "tests/forex/test_early_exit.py",
        tests: 12,
        covers: "Phase 1b dynamic management: progress vs time_band modes, R-unit math, min_bars gating",
      },
      {
        file: "tests/forex/test_data.py",
        tests: 10,
        covers: "yfinance cache (hit/miss/partial/stale), upsert dedup, weekly W-FRI resample aggregation",
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
        tests: 33,
        covers: "Portfolio CRUD lifecycle at /portfolios/*, input validation (422), 404 handling, CSV export, target field nulling; _total_budgets() float type invariant; oversight-activity endpoint (7 cases); decision mode CRUD + audit trail (5 cases)",
      },
      {
        file: "tests/test_executor_decision_modes.py",
        tests: 6,
        covers: "Executor decision-mode branching: claude_decides calls Claude, rules_decide never calls Claude, rules_with_claude_oversight calls both + logs rules_recommendation, trading constraints still block rules-mode signals",
      },
      {
        file: "tests/earnings/test_routes.py",
        tests: 6,
        covers: "Earnings calendar GET, symbol lookup, day bounds validation, refresh error sanitization",
      },
      {
        file: "tests/test_trades_routes.py",
        tests: 6,
        covers: "/trades includes portfolio trades, /trades/export, pagination behavior, block-stats endpoint",
      },
      {
        file: "tests/test_portfolio_routes.py",
        tests: 5,
        covers: "Snapshots, metrics with Decimal data, insufficient data handling, /health",
      },
      {
        file: "tests/test_bot_routes.py",
        tests: 6,
        covers: "Bot status (active/total portfolios shape), executed trade count, last run, full portfolio lifecycle E2E",
      },
      {
        file: "tests/test_backtest_routes.py",
        tests: 13,
        covers: "Strategies list, backtest CRUD, pending status, config retrieval, delete, validation",
      },
      {
        file: "tests/test_todos_routes.py",
        tests: 18,
        covers: "Todo CRUD with JSON persistence isolation, status filter, validation, 422/404 handling",
      },
      {
        file: "tests/forex/test_routes.py",
        tests: 6,
        covers: "Forex backtest CRUD, validation (date order, unknown symbol), background runner stub",
      },
      {
        file: "tests/plans/test_fetch_market_data.py",
        tests: 3,
        covers: "fetch_market_data folds strategy_params['tickers'] into the claude_decides universe; malformed (non-list) param ignored, not char-splatted; AV quotes scoped to held positions only (not fanned over the universe)",
      },
      {
        file: "tests/test_backtest_data.py",
        tests: 5,
        covers: "fetch_and_cache_bars OHLCV pipeline (real SQLite cache, mocked Alpaca): gap-fill skips fully-cached tickers, all-cached never calls Alpaca, uncached tickers fetched in one multi-symbol batch; load_bars issues ONE grouped query regardless of ticker count + DataFrame shape/order",
      },
      {
        file: "tests/plans/test_screener_feed.py",
        tests: 6,
        covers: "Screener→portfolio feed: opted-in plan gets top-N tickers + ranked CSV, non-opted plan gets neither, failed runs ignored, latest complete run wins, screener_top_n sanitized (cap 40, junk→0), CSV gated per plan in run_plan_cycle",
      },
      {
        file: "tests/plans/test_exit_only_cycle.py",
        tests: 7,
        covers: "3:30 PM exit-only cycle: buys suppressed to holds for claude_decides AND rules modes (single executor enforcement point), sells still execute, normal cycles unaffected; virtual positions carry real cost basis + unrealized P&L (average-cost method: buys re-average, sells don't, closed positions drop out)",
      },
      {
        file: "tests/screener/test_run_screener.py",
        tests: 2,
        covers: "run_screener orchestration: success persists ranked candidates + status=complete; failing data fetch marks status=failed (not stuck running) + records error",
      },
      {
        file: "tests/screener/test_routes.py",
        tests: 3,
        covers: "/screener returns latest complete run + ranked candidates, empty state, background refresh trigger",
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
        tests: 8,
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
        file: "src/app/trades/page.test.tsx",
        tests: 7,
        covers: "Trade list rendering, pagination (load more), auth guard, CSV export, empty state, error state",
      },
      {
        file: "src/components/PortfolioAllocationChart.test.tsx",
        tests: 5,
        covers: "Empty state, chart rendering, total budget, percentages, legend click handler",
      },
      {
        file: "src/components/PortfolioPositions.test.tsx",
        tests: 10,
        covers: "Loading state, error state, empty state, positions table, total calculations, P&L rendering, refetch on prop change",
      },
      {
        file: "src/components/TradeTable.test.tsx",
        tests: 12,
        covers: "Table rendering, Passed/Blocked badges, BUY/SELL/HOLD colors, confidence %, sorting, reasoning column",
      },
      {
        file: "src/components/ConfirmModal.test.tsx",
        tests: 7,
        covers: "Open/close, title/message, confirm/cancel callbacks, custom labels, backdrop click",
      },
      {
        file: "src/components/KillSwitchButton.test.tsx",
        tests: 6,
        covers: "Pause/resume portfolio states, updatePortfolio API calls, loading states, cancel without API call",
      },
      {
        file: "src/components/TopNav.test.tsx",
        tests: 11,
        covers: "All four group triggers (Core/Trading/Forex/Admin), brand mark, mega-menu open/close, item descriptions, Esc, toggle, aria-expanded, search/notifications/theme/mobile chrome",
      },
      {
        file: "src/components/DecisionModeBadge.test.tsx",
        tests: 6,
        covers: "Renders correct label and color for each decision mode (claude_decides, rules_decide, rules_with_claude_oversight); strategy name shown when provided",
      },
      {
        file: "src/app/portfolios/[id]/strategy/page.test.tsx",
        tests: 8,
        covers: "Decision Engine page: current mode badge on load, confirmation modal on mode switch, mode change apply/cancel, error when rules mode saved without strategy, manual ticker override (parsed + uppercased) save + pre-fill in claude_decides mode",
      },
      {
        file: "src/app/portfolios/[id]/oversight/page.test.tsx",
        tests: 6,
        covers: "Oversight Activity page: empty state, summary stat cards, Confirmed/Overridden badges, ticker + signal display, API error state",
      },
      {
        file: "src/app/portfolios/new/page.test.tsx",
        tests: 5,
        covers: "New portfolio form: rules_decide requires strategy selection, invalid submission blocked, valid claude_decides submission proceeds",
      },
      {
        file: "src/app/portfolios/page.test.tsx",
        tests: 13,
        covers: "Portfolio list: Pause/Resume toggle (shows correct label, calls updatePortfolio with correct is_active), delete confirm flow, loading state, error state, empty state",
      },
      {
        file: "src/components/AccountHoldings.test.tsx",
        tests: 4,
        covers: "Account holdings table: cost basis derived from shares × avg price (not market value), fractional share formatting, sort by market value desc, empty state",
      },
      {
        file: "src/app/screener/page.test.tsx",
        tests: 3,
        covers: "Screener page: empty state, ranked candidates with formatted factor percentages, background refresh trigger + notice",
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
  { cmd: "npm run test:backend", desc: "All backend tests (382 tests)" },
  { cmd: "npm run test:frontend", desc: "All frontend tests (129 tests)" },
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
        <div className="bz-glass p-4">
          <p className="text-xs text-muted">Total Tests</p>
          <p className="mt-1 text-2xl font-bold text-primary">{totalTests}</p>
        </div>
        <div className="bz-glass p-4">
          <p className="text-xs text-muted">Test Suites</p>
          <p className="mt-1 text-2xl font-bold text-primary">{totalSuites}</p>
        </div>
        <div className="bz-glass p-4">
          <p className="text-xs text-muted">Categories</p>
          <p className="mt-1 text-2xl font-bold text-accent">{implemented} active</p>
          <p className="mt-0.5 text-[10px] text-muted">{planned} planned</p>
        </div>
        <div className="bz-glass p-4">
          <p className="text-xs text-muted">Run Time</p>
          <p className="mt-1 text-2xl font-bold text-primary">~5s</p>
          <p className="mt-0.5 text-[10px] text-muted">full suite</p>
        </div>
      </div>

      {/* Test types explained */}
      <div className="mb-8 bz-glass p-6">
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
      <div className="mb-8 bz-glass p-6">
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
                <td className="px-3 py-2 text-secondary">tsc + eslint + pytest (328) + vitest (120)</td>
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
      <div className="mb-8 bz-glass p-6">
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
        <div key={category} className="mb-6 bz-glass">
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
                    <span className="rounded bg-pos/15 px-2 py-0.5 text-[10px] font-medium text-pos">
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
