"use client";

import { useEffect, useState } from "react";
import { getScreener, refreshScreener } from "@/lib/api";
import type { ScreenerResult } from "@/lib/types";
import { formatCurrency, formatDateTime } from "@/lib/utils";

function pct(v: number): string {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

export default function ScreenerPage() {
  const [data, setData] = useState<ScreenerResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      setData(await getScreener());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load screener");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleRefresh() {
    try {
      setRefreshing(true);
      setNotice(null);
      await refreshScreener();
      setNotice("Screening started — it scans ~500 names in the background (~1-2 min). Reload to see fresh results.");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Failed to start screener");
    } finally {
      setRefreshing(false);
    }
  }

  const run = data?.run ?? null;
  const candidates = data?.candidates ?? [];

  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold">Screener</h1>
          <p className="text-muted mt-2">
            Daily ranking of ~500 S&amp;P 500 names by momentum, relative strength, trend, and volatility.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {refreshing ? "Starting…" : "Refresh"}
        </button>
      </div>

      <div className="mb-6 rounded-lg border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-secondary">
        <strong className="text-primary">Advisory only.</strong> This ranking is research — it does not place
        trades or change any strategy&apos;s universe. It shows what a momentum/trend screen surfaces today.
      </div>

      {notice && (
        <div className="mb-6 rounded-lg bg-card-alt px-4 py-3 text-sm text-secondary">{notice}</div>
      )}

      {loading ? (
        <div className="text-muted">Loading screener…</div>
      ) : error ? (
        <div className="p-4 bg-red-100 text-red-800 rounded-lg">{error}</div>
      ) : !run || candidates.length === 0 ? (
        <div className="text-center py-12 bz-glass rounded-xl">
          <p className="text-muted mb-2">No screen has run yet.</p>
          <p className="text-sm text-muted">
            It runs automatically each weekday at 7:30 AM ET, or hit Refresh to run it now.
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted mb-4">
            Last run {formatDateTime(run.run_at)} · {run.scored_count} ranked of {run.universe_size} screened
            {data?.refreshing && " · a new run is in progress…"}
          </p>
          <div className="bz-glass rounded-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-border">
                  <th className="px-4 py-3 font-medium">#</th>
                  <th className="px-4 py-3 font-medium">Ticker</th>
                  <th className="px-4 py-3 text-right font-medium">Price</th>
                  <th className="px-4 py-3 text-right font-medium">Score</th>
                  <th className="px-4 py-3 text-right font-medium">Momentum</th>
                  <th className="px-4 py-3 text-right font-medium">vs SPY</th>
                  <th className="px-4 py-3 text-right font-medium">Trend</th>
                  <th className="px-4 py-3 text-right font-medium">RSI</th>
                  <th className="px-4 py-3 text-right font-medium">Volatility</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.ticker} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 text-muted">{c.rank}</td>
                    <td className="px-4 py-3 font-medium text-primary">{c.ticker}</td>
                    <td className="px-4 py-3 text-right text-secondary">{formatCurrency(c.price)}</td>
                    <td className="px-4 py-3 text-right font-medium text-primary">{c.composite_score.toFixed(2)}</td>
                    <td className={`px-4 py-3 text-right ${c.momentum >= 0 ? "text-pos" : "text-neg"}`}>{pct(c.momentum)}</td>
                    <td className={`px-4 py-3 text-right ${c.rel_strength >= 0 ? "text-pos" : "text-neg"}`}>{pct(c.rel_strength)}</td>
                    <td className="px-4 py-3 text-right text-secondary">{c.trend_score.toFixed(1)}</td>
                    <td className="px-4 py-3 text-right text-secondary">{c.rsi.toFixed(0)}</td>
                    <td className="px-4 py-3 text-right text-secondary">{(c.volatility * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
