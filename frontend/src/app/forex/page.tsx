"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  createForexBacktest,
  deleteForexBacktest,
  getForexBacktest,
  getForexSymbols,
  listForexBacktests,
} from "@/lib/api";
import {
  ForexBacktestDetail,
  ForexBacktestSummary,
  ForexEarlyExitMode,
} from "@/lib/types";
import dynamic from "next/dynamic";

const ForexEquityChart = dynamic(() => import("./EquityChart"), { ssr: false });

const SUPPORTED = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"];

export default function ForexPage() {
  const { user } = useAuth();
  const [runs, setRuns] = useState<ForexBacktestSummary[]>([]);
  const [supported, setSupported] = useState<string[]>(SUPPORTED);
  const [detail, setDetail] = useState<ForexBacktestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [pollingId, setPollingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ── Form state (persisted to localStorage so the buddy doesn't re-key on refresh)
  const [name, setName] = useState("");
  const [symbols, setSymbols] = useState<string[]>(["EURUSD", "GBPUSD", "USDJPY"]);
  const [startDate, setStartDate] = useState("2018-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [initialEquity, setInitialEquity] = useState(10000);
  const [riskPct, setRiskPct] = useState(0.02);
  const [slBufferPct, setSlBufferPct] = useState(0.001);
  const [pivotLookback, setPivotLookback] = useState(100);
  const [clusterPct, setClusterPct] = useState(0.005);
  const [earlyExitMode, setEarlyExitMode] = useState<ForexEarlyExitMode>("none");
  const [earlyExitMinBars, setEarlyExitMinBars] = useState(10);
  const [earlyExitThresholdR, setEarlyExitThresholdR] = useState(0.3);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("forex-form");
    if (saved) {
      try {
        const v = JSON.parse(saved);
        if (v.symbols) setSymbols(v.symbols);
        if (v.startDate) setStartDate(v.startDate);
        if (v.endDate) setEndDate(v.endDate);
        if (typeof v.initialEquity === "number") setInitialEquity(v.initialEquity);
        if (typeof v.riskPct === "number") setRiskPct(v.riskPct);
        if (typeof v.slBufferPct === "number") setSlBufferPct(v.slBufferPct);
        if (typeof v.pivotLookback === "number") setPivotLookback(v.pivotLookback);
        if (typeof v.clusterPct === "number") setClusterPct(v.clusterPct);
        if (v.earlyExitMode) setEarlyExitMode(v.earlyExitMode);
        if (typeof v.earlyExitMinBars === "number") setEarlyExitMinBars(v.earlyExitMinBars);
        if (typeof v.earlyExitThresholdR === "number") setEarlyExitThresholdR(v.earlyExitThresholdR);
      } catch {
        /* ignore parse errors */
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(
      "forex-form",
      JSON.stringify({
        symbols, startDate, endDate, initialEquity, riskPct, slBufferPct,
        pivotLookback, clusterPct, earlyExitMode, earlyExitMinBars, earlyExitThresholdR,
      }),
    );
  }, [
    symbols, startDate, endDate, initialEquity, riskPct, slBufferPct,
    pivotLookback, clusterPct, earlyExitMode, earlyExitMinBars, earlyExitThresholdR,
  ]);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      getForexSymbols().catch(() => SUPPORTED),
      listForexBacktests().catch(() => []),
    ])
      .then(([s, r]) => {
        setSupported(s.length ? s : SUPPORTED);
        setRuns(r);
      })
      .finally(() => setLoading(false));
  }, [user]);

  // Poll a running backtest until it completes.
  useEffect(() => {
    if (pollingId === null) return;
    const interval = setInterval(async () => {
      try {
        const d = await getForexBacktest(pollingId);
        if (d.status === "completed" || d.status === "failed") {
          setPollingId(null);
          setRunning(false);
          setDetail(d);
          const fresh = await listForexBacktests().catch(() => []);
          setRuns(fresh);
          if (d.status === "failed") {
            setError(d.error_message || "Run failed");
          }
        }
      } catch {
        setPollingId(null);
        setRunning(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [pollingId]);

  function toggleSymbol(s: string) {
    setSymbols((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
    );
  }

  async function handleRun() {
    if (!symbols.length) {
      setError("Select at least one currency pair");
      return;
    }
    setError(null);
    setRunning(true);
    try {
      const res = await createForexBacktest({
        name: name || `${symbols.join(",")} ${startDate} → ${endDate}`,
        symbols,
        start_date: startDate,
        end_date: endDate,
        initial_equity: initialEquity,
        risk_pct: riskPct,
        sl_buffer_pct: slBufferPct,
        pivot_lookback_weeks: pivotLookback,
        cluster_pct: clusterPct,
        early_exit_mode: earlyExitMode,
        early_exit_min_bars: earlyExitMinBars,
        early_exit_threshold_r: earlyExitThresholdR,
      });
      setPollingId(res.run_id);
      setName("");
    } catch (e) {
      setRunning(false);
      setError(e instanceof Error ? e.message : "Failed to create backtest");
    }
  }

  async function handleView(item: ForexBacktestSummary) {
    if (item.status !== "completed") return;
    try {
      const d = await getForexBacktest(item.id);
      setDetail(d);
    } catch {
      /* ignore */
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this backtest run?")) return;
    try {
      await deleteForexBacktest(id);
      setRuns((prev) => prev.filter((r) => r.id !== id));
      if (detail?.id === id) setDetail(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const sortedTrades = useMemo(() => {
    if (!detail) return [];
    return [...detail.trades_log].sort((a, b) =>
      a.exit_date < b.exit_date ? 1 : -1,
    );
  }, [detail]);

  if (!user) {
    return (
      <div className="p-6 text-secondary">Sign in to use the forex tool.</div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-primary">Forex Swing-Zone Backtest</h1>
        <p className="mt-1 text-sm text-secondary">
          Pure rules-based: weekly support/resistance zones → daily reversal pattern entry → 1:1 RR.
          Tweak parameters, run, compare. Independent tool — does not touch the Claude trader.
        </p>
      </header>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* ── Configuration panel ────────────────────────────── */}
      <section className="bz-glass-soft p-5 space-y-4">
        <h2 className="text-lg font-medium text-primary">Configuration</h2>

        {/* Symbols */}
        <div>
          <label className="block text-xs font-medium text-secondary mb-2">
            Currency Pairs
          </label>
          <div className="flex flex-wrap gap-2">
            {supported.map((s) => {
              const on = symbols.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleSymbol(s)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium border transition-colors ${
                    on
                      ? "border-pos bg-pos/15 text-pos"
                      : "border-border bg-card-alt text-secondary hover:border-pos/50"
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </div>

        {/* Core fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Field label="Run Name (optional)">
            <input
              className="input"
              value={name}
              placeholder="e.g. baseline-2018-2025"
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="Start Date">
            <input
              type="date"
              className="input"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </Field>
          <Field label="End Date">
            <input
              type="date"
              className="input"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </Field>
          <Field label="Initial Equity (USD)">
            <input
              type="number"
              className="input"
              value={initialEquity}
              min={100}
              onChange={(e) => setInitialEquity(Number(e.target.value))}
            />
          </Field>
          <Field label="Risk per Trade (%)">
            <input
              type="number"
              step="0.01"
              className="input"
              value={riskPct * 100}
              onChange={(e) => setRiskPct(Number(e.target.value) / 100)}
            />
          </Field>
          <Field label="SL Buffer (%)">
            <input
              type="number"
              step="0.01"
              className="input"
              value={slBufferPct * 100}
              onChange={(e) => setSlBufferPct(Number(e.target.value) / 100)}
            />
          </Field>
          <Field label="Pivot Lookback (weeks)">
            <input
              type="number"
              className="input"
              value={pivotLookback}
              min={10}
              max={500}
              onChange={(e) => setPivotLookback(Number(e.target.value))}
            />
          </Field>
          <Field label="Cluster Tolerance (%)">
            <input
              type="number"
              step="0.01"
              className="input"
              value={clusterPct * 100}
              onChange={(e) => setClusterPct(Number(e.target.value) / 100)}
            />
          </Field>
        </div>

        {/* Advanced — Phase 1b early exit */}
        <details
          open={advancedOpen}
          onToggle={(e) => setAdvancedOpen((e.target as HTMLDetailsElement).open)}
          className="border-t border-border pt-4"
        >
          <summary className="cursor-pointer text-sm font-medium text-secondary hover:text-primary">
            Dynamic Management (early exit)
          </summary>
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field label="Mode">
              <select
                className="input"
                value={earlyExitMode}
                onChange={(e) => setEarlyExitMode(e.target.value as ForexEarlyExitMode)}
              >
                <option value="none">none — strict rules only</option>
                <option value="progress">progress — close if no progress to TP</option>
                <option value="time_band">time_band — close if meandering near zero</option>
              </select>
            </Field>
            <Field label="Min Bars Before Eligible">
              <input
                type="number"
                className="input"
                value={earlyExitMinBars}
                min={1}
                max={200}
                onChange={(e) => setEarlyExitMinBars(Number(e.target.value))}
              />
            </Field>
            <Field label="Threshold (R units)">
              <input
                type="number"
                step="0.05"
                className="input"
                value={earlyExitThresholdR}
                min={0}
                max={1}
                onChange={(e) => setEarlyExitThresholdR(Number(e.target.value))}
              />
            </Field>
          </div>
        </details>

        <div className="flex justify-end">
          <button
            type="button"
            disabled={running || !symbols.length}
            onClick={handleRun}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? "Running..." : "Run Backtest"}
          </button>
        </div>
      </section>

      {/* ── Past Runs ──────────────────────────────────────── */}
      <section className="bz-glass-soft p-5">
        <h2 className="text-lg font-medium text-primary mb-3">Past Runs</h2>
        {loading ? (
          <p className="text-sm text-secondary">Loading...</p>
        ) : runs.length === 0 ? (
          <p className="text-sm text-secondary">
            No backtests yet. Configure parameters above and click Run.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted">
                  <th className="px-2 py-2">Name</th>
                  <th className="px-2 py-2">Symbols</th>
                  <th className="px-2 py-2">Window</th>
                  <th className="px-2 py-2 text-right">Trades</th>
                  <th className="px-2 py-2 text-right">Return</th>
                  <th className="px-2 py-2 text-right">Win Rate</th>
                  <th className="px-2 py-2 text-right">PF</th>
                  <th className="px-2 py-2 text-right">Max DD</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr
                    key={r.id}
                    className={`border-t border-border ${
                      r.status === "completed" ? "cursor-pointer hover:bg-card-alt" : ""
                    } ${detail?.id === r.id ? "bg-card-alt" : ""}`}
                    onClick={() => handleView(r)}
                  >
                    <td className="px-2 py-2 text-primary">{r.name}</td>
                    <td className="px-2 py-2 text-secondary">{r.symbols.join(", ")}</td>
                    <td className="px-2 py-2 text-secondary">
                      {r.start_date} → {r.end_date}
                    </td>
                    <td className="px-2 py-2 text-right text-secondary">
                      {r.total_trades ?? "—"}
                    </td>
                    <td
                      className={`px-2 py-2 text-right font-medium ${
                        r.total_return_pct == null
                          ? "text-secondary"
                          : r.total_return_pct >= 0
                          ? "text-pos"
                          : "text-red-400"
                      }`}
                    >
                      {r.total_return_pct == null
                        ? "—"
                        : `${r.total_return_pct >= 0 ? "+" : ""}${r.total_return_pct.toFixed(2)}%`}
                    </td>
                    <td className="px-2 py-2 text-right text-secondary">
                      {r.win_rate_pct == null ? "—" : `${r.win_rate_pct.toFixed(1)}%`}
                    </td>
                    <td className="px-2 py-2 text-right text-secondary">
                      {r.profit_factor == null ? "—" : r.profit_factor.toFixed(2)}
                    </td>
                    <td className="px-2 py-2 text-right text-secondary">
                      {r.max_drawdown_pct == null ? "—" : `${r.max_drawdown_pct.toFixed(1)}%`}
                    </td>
                    <td className="px-2 py-2">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(r.id);
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
        )}
      </section>

      {/* ── Detail ─────────────────────────────────────────── */}
      {detail && (
        <section className="bz-glass-soft p-5 space-y-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-medium text-primary">{detail.name}</h2>
            <button
              type="button"
              onClick={() => setDetail(null)}
              className="text-xs text-muted hover:text-primary"
            >
              Close
            </button>
          </div>
          <p className="text-xs text-muted">
            {detail.symbols.join(", ")} · {detail.start_date} → {detail.end_date} ·
            risk {(detail.risk_pct * 100).toFixed(1)}% · early-exit{" "}
            <span className="font-mono">{detail.early_exit_mode}</span>
          </p>

          {/* Stats grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Stat label="Final Equity" value={`$${(detail.final_equity ?? 0).toFixed(0)}`} />
            <Stat
              label="Return"
              value={`${(detail.total_return_pct ?? 0) >= 0 ? "+" : ""}${(detail.total_return_pct ?? 0).toFixed(2)}%`}
              tone={(detail.total_return_pct ?? 0) >= 0 ? "good" : "bad"}
            />
            <Stat label="Trades" value={`${detail.total_trades ?? 0}`} />
            <Stat label="Win Rate" value={`${(detail.win_rate_pct ?? 0).toFixed(1)}%`} />
            <Stat label="Profit Factor" value={(detail.profit_factor ?? 0).toFixed(2)} />
            <Stat label="Max Drawdown" value={`${(detail.max_drawdown_pct ?? 0).toFixed(1)}%`} />
          </div>

          {/* Equity curve */}
          {detail.equity_curve.length > 0 && (
            <div className="h-64">
              <ForexEquityChart data={detail.equity_curve} initial={detail.initial_equity} />
            </div>
          )}

          {/* Trades log */}
          {sortedTrades.length > 0 && (
            <div className="overflow-x-auto">
              <h3 className="mb-2 text-sm font-medium text-secondary">
                Trades ({sortedTrades.length})
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left uppercase text-muted">
                    <th className="px-2 py-1.5">Symbol</th>
                    <th className="px-2 py-1.5">Dir</th>
                    <th className="px-2 py-1.5">Entry</th>
                    <th className="px-2 py-1.5">Exit</th>
                    <th className="px-2 py-1.5 text-right">Entry Px</th>
                    <th className="px-2 py-1.5 text-right">Exit Px</th>
                    <th className="px-2 py-1.5 text-right">PnL</th>
                    <th className="px-2 py-1.5">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedTrades.slice(0, 50).map((t, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="px-2 py-1.5 text-primary">{t.symbol}</td>
                      <td className="px-2 py-1.5 text-secondary">{t.direction}</td>
                      <td className="px-2 py-1.5 text-secondary">{t.entry_date}</td>
                      <td className="px-2 py-1.5 text-secondary">{t.exit_date}</td>
                      <td className="px-2 py-1.5 text-right text-secondary">
                        {t.entry_price.toFixed(5)}
                      </td>
                      <td className="px-2 py-1.5 text-right text-secondary">
                        {t.exit_price.toFixed(5)}
                      </td>
                      <td
                        className={`px-2 py-1.5 text-right font-medium ${
                          t.pnl_usd >= 0 ? "text-pos" : "text-red-400"
                        }`}
                      >
                        {t.pnl_usd >= 0 ? "+" : ""}${t.pnl_usd.toFixed(2)}
                      </td>
                      <td className="px-2 py-1.5 text-muted text-xs">{t.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {sortedTrades.length > 50 && (
                <p className="mt-2 text-xs text-muted">
                  Showing 50 most recent of {sortedTrades.length} trades.
                </p>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-secondary mb-1">{label}</span>
      {children}
    </label>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "bad";
}) {
  const color =
    tone === "good"
      ? "text-pos"
      : tone === "bad"
      ? "text-red-400"
      : "text-primary";
  return (
    <div className="rounded-md border border-border bg-card-alt p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-1 text-base font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
    running: "bg-blue-500/15 text-blue-300 border-blue-500/30",
    completed: "bg-pos/15 text-pos border-pos/30",
    failed: "bg-red-500/15 text-red-300 border-red-500/30",
  };
  const cls = map[status] ?? "bg-card-alt text-secondary border-border";
  return (
    <span className={`inline-block rounded-md border px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
