"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  createBacktest,
  deleteBacktest,
  getBacktestResult,
  getStrategies,
  listBacktests,
} from "@/lib/api";
import { BacktestDetail, BacktestItem, StrategyInfo } from "@/lib/types";
import Spinner from "@/components/Spinner";
import Tip from "@/components/Tip";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function BacktestPage() {
  const { user } = useAuth();
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [backtests, setBacktests] = useState<BacktestItem[]>([]);
  const [detail, setDetail] = useState<BacktestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [pollingId, setPollingId] = useState<number | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState("sma_crossover");
  const [tickers, setTickers] = useState("SPY, QQQ, AAPL, MSFT, NVDA");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2026-04-01");
  const [capital, setCapital] = useState(100000);
  const [maxPosPct, setMaxPosPct] = useState(0.1);
  const [maxPositions, setMaxPositions] = useState(10);
  const [stopLoss, setStopLoss] = useState(0.05);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      getStrategies().catch(() => []),
      listBacktests().catch(() => []),
    ])
      .then(([s, b]) => {
        setStrategies(s);
        setBacktests(b);
      })
      .finally(() => setLoading(false));
  }, [user]);

  // Poll running backtests
  useEffect(() => {
    if (pollingId === null) return;
    const interval = setInterval(async () => {
      try {
        const result = await getBacktestResult(pollingId);
        if (result.status === "completed" || result.status === "failed") {
          setPollingId(null);
          setRunning(false);
          setDetail(result);
          const fresh = await listBacktests().catch(() => []);
          setBacktests(fresh);
        }
      } catch {
        setPollingId(null);
        setRunning(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [pollingId]);

  async function handleRun() {
    const tickerList = tickers
      .split(",")
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (!tickerList.length) return;

    setRunning(true);
    try {
      const selectedStrategy = strategies.find((s) => s.id === strategy);
      const params: Record<string, unknown> = {};
      if (selectedStrategy) {
        for (const p of selectedStrategy.params) {
          params[p.key] = p.default;
        }
      }

      const res = await createBacktest({
        name: name || `${strategy} — ${tickerList.join(", ")}`,
        strategy,
        tickers: tickerList,
        start_date: startDate,
        end_date: endDate,
        initial_capital: capital,
        params,
        max_position_pct: maxPosPct,
        max_positions: maxPositions,
        stop_loss_pct: stopLoss,
      });
      setPollingId(res.result_id);
    } catch (e) {
      setRunning(false);
      alert(e instanceof Error ? e.message : "Failed to create backtest");
    }
  }

  async function handleViewResult(item: BacktestItem) {
    if (item.status !== "completed") return;
    try {
      const result = await getBacktestResult(item.id);
      setDetail(result);
    } catch {
      // ignore
    }
  }

  async function handleDelete(configId: number) {
    await deleteBacktest(configId).catch(() => {});
    setBacktests((prev) => prev.filter((b) => b.config_id !== configId));
    if (detail && detail.config_id === configId) setDetail(null);
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const selectedStrategy = strategies.find((s) => s.id === strategy);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold text-primary">Backtest</h1>
        <Tip text="Backtesting lets you test 'what would have happened?' by running a trading strategy on historical stock prices. It doesn't use real money — it simulates trades to see if a strategy would have been profitable." />
      </div>
      <p className="mt-1 text-sm text-muted">
        Test trading strategies against historical data
      </p>

      {/* Config Form */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <h2 className="mb-4 text-sm font-semibold text-primary">
          New Backtest
        </h2>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-muted">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My backtest"
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary placeholder-zinc-600 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 flex items-center gap-1 text-xs text-muted">
              Strategy <Tip text="The rule set the simulation follows. SMA Crossover buys when short-term momentum beats long-term (bullish signal). RSI Mean Reversion buys oversold stocks and sells overbought ones. Buy &amp; Hold is the simplest benchmark — just buy and hold." />
            </label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary focus:border-emerald-500 focus:outline-none"
            >
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {selectedStrategy && (
              <p className="mt-1 text-xs text-muted">
                {selectedStrategy.description}
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted">
              Tickers (comma-separated)
            </label>
            <input
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary placeholder-zinc-600 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted">
              Initial Capital ($)
            </label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 flex items-center gap-1 text-xs text-muted">
              Max Position Size (%) <Tip text="The most you'll put into any single stock, as a fraction of your total portfolio. 0.10 means 10% — so with $100K, no single stock gets more than $10K." />
            </label>
            <input
              type="number"
              step="0.01"
              value={maxPosPct}
              onChange={(e) => setMaxPosPct(Number(e.target.value))}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted">
              Max Positions
            </label>
            <input
              type="number"
              value={maxPositions}
              onChange={(e) => setMaxPositions(Number(e.target.value))}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 flex items-center gap-1 text-xs text-muted">
              Stop Loss (%) <Tip text="If a stock drops this much from your buy price, it auto-sells to limit your loss. 0.05 means 5% — if you bought at $100 and it drops to $95, it sells automatically." />
            </label>
            <input
              type="number"
              step="0.01"
              value={stopLoss}
              onChange={(e) => setStopLoss(Number(e.target.value))}
              className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary focus:border-emerald-500 focus:outline-none"
            />
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={running}
          className="mt-4 rounded-lg bg-emerald-600 px-6 py-2.5 text-sm font-medium text-primary transition-colors hover:bg-emerald-500 disabled:opacity-50"
        >
          {running ? (
            <span className="flex items-center gap-2">
              <Spinner /> Running Backtest...
            </span>
          ) : (
            "Run Backtest"
          )}
        </button>
      </div>

      {/* Past Backtests */}
      {backtests.length > 0 && (
        <div className="mt-6 rounded-xl border border-border bg-card p-6">
          <h2 className="mb-4 text-sm font-semibold text-primary">
            Past Backtests
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted">
                  <th className="pb-2 pr-4">Name</th>
                  <th className="pb-2 pr-4">Strategy</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4 text-right">Return</th>
                  <th className="pb-2 pr-4 text-right">Sharpe</th>
                  <th className="pb-2 pr-4 text-right">Drawdown</th>
                  <th className="pb-2 pr-4 text-right">Trades</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {backtests.map((bt) => (
                  <tr
                    key={bt.config_id ?? bt.id}
                    onClick={() => handleViewResult(bt)}
                    className={`border-b border-border/50 transition-colors ${
                      bt.status === "completed"
                        ? "cursor-pointer hover:bg-card-alt/50"
                        : ""
                    }`}
                  >
                    <td className="py-2.5 pr-4 text-primary">{bt.name}</td>
                    <td className="py-2.5 pr-4 text-secondary">
                      {bt.strategy.replace(/_/g, " ")}
                    </td>
                    <td className="py-2.5 pr-4">
                      <StatusBadge status={bt.status} />
                    </td>
                    <td
                      className={`py-2.5 pr-4 text-right ${
                        bt.total_return_pct !== null
                          ? bt.total_return_pct >= 0
                            ? "text-accent"
                            : "text-red-400"
                          : "text-muted"
                      }`}
                    >
                      {bt.total_return_pct !== null
                        ? `${bt.total_return_pct >= 0 ? "+" : ""}${bt.total_return_pct}%`
                        : "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-secondary">
                      {bt.sharpe_ratio ?? "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-secondary">
                      {bt.max_drawdown_pct !== null
                        ? `${bt.max_drawdown_pct}%`
                        : "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-secondary">
                      {bt.total_trades ?? "—"}
                    </td>
                    <td className="py-2.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(bt.config_id ?? bt.id);
                        }}
                        className="text-xs text-muted hover:text-red-400"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Result Detail */}
      {detail && detail.status === "completed" && (
        <div className="mt-6 space-y-6">
          {/* Metrics */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total Return"
              value={`${(detail.total_return_pct ?? 0) >= 0 ? "+" : ""}${detail.total_return_pct}%`}
              color={
                (detail.total_return_pct ?? 0) >= 0
                  ? "text-accent"
                  : "text-red-400"
              }
              tip="How much the simulated portfolio gained or lost over the backtest period. Compare this to Buy & Hold to see if the strategy adds value."
            />
            <MetricCard
              label="Sharpe Ratio"
              value={detail.sharpe_ratio?.toString() ?? "—"}
              color={
                detail.sharpe_ratio === null
                  ? "text-secondary"
                  : detail.sharpe_ratio >= 1
                    ? "text-accent"
                    : detail.sharpe_ratio >= 0
                      ? "text-amber-400"
                      : "text-red-400"
              }
              tip="Return per unit of risk. Above 1.0 = good risk-adjusted returns. Above 2.0 = excellent. Compare across strategies to find the best risk/reward balance."
            />
            <MetricCard
              label="Max Drawdown"
              value={`${detail.max_drawdown_pct}%`}
              color="text-amber-400"
            />
            <MetricCard
              label="Win Rate"
              value={`${detail.win_rate_pct}%`}
              color={
                (detail.win_rate_pct ?? 0) >= 55
                  ? "text-accent"
                  : "text-amber-400"
              }
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <MetricCard
              label="Sortino Ratio"
              value={detail.sortino_ratio?.toString() ?? "—"}
              color="text-blue-400"
            />
            <MetricCard
              label="Profit Factor"
              value={detail.profit_factor?.toString() ?? "—"}
              color="text-blue-400"
            />
            <MetricCard
              label="Total Trades"
              value={detail.total_trades?.toString() ?? "0"}
              color="text-primary"
            />
          </div>

          {/* Equity Curve */}
          {detail.equity_curve.length > 1 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="mb-4 text-sm font-semibold text-primary">
                Equity Curve
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart
                  data={detail.equity_curve.map((pt) => ({
                    date: pt.date.slice(5),
                    equity: pt.equity,
                  }))}
                >
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#71717a", fontSize: 10 }}
                    axisLine={{ stroke: "#3f3f46" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "#71717a", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) =>
                      `$${(v / 1000).toFixed(0)}k`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #3f3f46",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value) => [
                      `$${Number(value).toLocaleString()}`,
                      "Equity",
                    ]}
                  />
                  <Line
                    dataKey="equity"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trades Table */}
          {detail.trades_log.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="mb-4 text-sm font-semibold text-primary">
                Simulated Trades ({detail.trades_log.length})
              </h3>
              <div className="max-h-96 overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs text-muted">
                      <th className="pb-2 pr-4">Date</th>
                      <th className="pb-2 pr-4">Ticker</th>
                      <th className="pb-2 pr-4">Action</th>
                      <th className="pb-2 pr-4 text-right">Qty</th>
                      <th className="pb-2 pr-4 text-right">Price</th>
                      <th className="pb-2">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.trades_log.map((t, i) => (
                      <tr
                        key={i}
                        className="border-b border-border/50"
                      >
                        <td className="py-2 pr-4 text-secondary">
                          {t.date}
                        </td>
                        <td className="py-2 pr-4 font-medium text-primary">
                          {t.ticker}
                        </td>
                        <td className="py-2 pr-4">
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-medium ${
                              t.action === "buy"
                                ? "bg-accent/10 text-accent"
                                : "bg-red-500/10 text-red-400"
                            }`}
                          >
                            {t.action.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-right text-secondary">
                          {t.quantity}
                        </td>
                        <td className="py-2 pr-4 text-right text-secondary">
                          ${t.price.toFixed(2)}
                        </td>
                        <td className="py-2 text-xs text-muted">
                          {t.reason}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error state */}
      {detail && detail.status === "failed" && (
        <div className="mt-6 rounded-xl border border-red-500/20 bg-red-500/5 p-6">
          <p className="text-sm font-medium text-red-400">Backtest Failed</p>
          <p className="mt-1 text-xs text-secondary">
            {detail.error_message}
          </p>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
  tip,
}: {
  label: string;
  value: string;
  color: string;
  tip?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <p className="flex items-center gap-1 text-xs text-muted">
        {label}
        {tip && <Tip text={tip} />}
      </p>
      <p className={`mt-2 text-3xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-zinc-500/10 text-secondary",
    running: "bg-blue-500/10 text-blue-400",
    completed: "bg-accent/10 text-accent",
    failed: "bg-red-500/10 text-red-400",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${
        styles[status] || styles.pending
      }`}
    >
      {status}
    </span>
  );
}
