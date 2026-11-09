"use client";

import { useEffect, useState } from "react";
import { getReport, getReports } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ReportRow, WeeklyReportDetail, WeeklyReportSummary } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function tone(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-muted";
  return v >= 0 ? "text-pos" : "text-neg";
}

function Verdict({ beat }: { beat: boolean | null }) {
  if (beat === null) return <span className="text-muted">No SPY data</span>;
  return beat ? (
    <span className="rounded-full bg-pos/10 px-2 py-0.5 text-xs font-medium text-pos">Beat SPY</span>
  ) : (
    <span className="rounded-full bg-neg/10 px-2 py-0.5 text-xs font-medium text-neg">Trailed SPY</span>
  );
}

function RowCard({ title, row }: { title: string; row: ReportRow }) {
  const c = row.costs;
  return (
    <section className="bz-glass rounded-2xl p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-primary">{title}</h2>
        <Verdict beat={row.beat_spy} />
      </div>

      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-muted">Return</dt>
          <dd className={`font-medium ${tone(row.return_pct)}`}>{pct(row.return_pct)}</dd>
        </div>
        <div>
          <dt className="text-muted">After costs</dt>
          <dd className={`font-semibold ${tone(row.after_cost_return_pct)}`}>{pct(row.after_cost_return_pct)}</dd>
        </div>
        <div>
          <dt className="text-muted">SPY</dt>
          <dd className={`font-medium ${tone(row.spy_return_pct)}`}>{pct(row.spy_return_pct)}</dd>
        </div>
        <div>
          <dt className="text-muted">Value</dt>
          <dd className="text-primary">{formatCurrency(row.end_value)}</dd>
        </div>
      </dl>

      {row.since_start && (
        <p className="mt-3 text-sm text-secondary">
          Since start: {pct(row.since_start.return_pct)} · after costs{" "}
          <span className={tone(row.since_start.after_cost_return_pct)}>{pct(row.since_start.after_cost_return_pct)}</span>{" "}
          · SPY {pct(row.since_start.spy_return_pct)}
        </p>
      )}

      <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
        <div>
          <h3 className="mb-1 font-medium text-primary">Trades</h3>
          <p className="text-secondary">
            {row.trades} trades · {row.wins} wins / {row.losses} losses
            {row.avg_win != null && ` · avg win ${formatCurrency(row.avg_win)}`}
            {row.avg_loss != null && ` · avg loss ${formatCurrency(row.avg_loss)}`}
          </p>
        </div>
        <div>
          <h3 className="mb-1 font-medium text-primary">Costs this week</h3>
          <p className="text-secondary">
            Spread {formatCurrency(c.spread)} · Fees {formatCurrency(c.fees)} · Claude {formatCurrency(c.api)} · Est. tax{" "}
            {formatCurrency(c.est_tax)} · <span className="text-primary">Total {formatCurrency(c.total)}</span>
          </p>
          {c.spread_unpriced_trades > 0 && (
            <p className="text-xs text-muted">{c.spread_unpriced_trades} trade(s) had no quote — spread not counted.</p>
          )}
        </div>
      </div>

      <div className="mt-4 text-sm">
        <h3 className="mb-1 font-medium text-primary">Safety limits that fired</h3>
        {row.limit_events.length === 0 ? (
          <p className="text-muted">None</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {row.limit_events.map((e) => (
              <li key={e.type} className="bz-glass-soft rounded-full px-3 py-1 text-secondary">
                {e.type} × {e.count}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default function ReportsPage() {
  const { user } = useAuth();
  const [list, setList] = useState<WeeklyReportSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<WeeklyReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getReports()
      .then((rows) => {
        if (cancelled) return;
        setList(rows);
        if (rows.length > 0) setSelected(rows[0].id);
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    if (!user || selected === null) return;
    let cancelled = false;
    setDetail(null);
    getReport(selected)
      .then((d) => !cancelled && setDetail(d))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [user, selected]);

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-bold text-primary">Weekly reports</h1>
        <p className="mt-1 text-sm text-secondary">
          Did each portfolio beat simply holding SPY, after spread, fees, the Claude bill and estimated tax? Written every
          Friday after the close.
        </p>
      </header>

      {error && <p className="bz-glass rounded-xl p-4 text-sm text-neg">{error}</p>}
      {loading && <p className="text-sm text-muted">Loading…</p>}

      {!loading && list.length === 0 && !error && (
        <p className="bz-glass rounded-2xl p-6 text-secondary">
          No reports yet — the first one is written Friday after the close.
        </p>
      )}

      {list.length > 0 && (
        <nav aria-label="Report weeks" className="flex flex-wrap gap-2">
          {list.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => setSelected(r.id)}
              className={`rounded-full px-3 py-1 text-sm ${
                r.id === selected ? "bg-accent-2 text-primary" : "bz-glass-soft text-secondary"
              }`}
            >
              Week ending {r.week_ending}
            </button>
          ))}
        </nav>
      )}

      {detail && (
        <>
          <section className="bz-glass rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-primary">Draft note (Claude) — review before acting</h2>
            <p className="mt-2 whitespace-pre-line text-sm text-secondary">
              {detail.note ?? "No note this week (the draft could not be generated)."}
            </p>
            <p className="mt-2 text-xs text-muted">
              Change at most one rule per portfolio per review, and log it in the experiment log.
            </p>
          </section>

          <RowCard title="Whole account" row={detail.payload.account} />
          {detail.payload.portfolios.map((row) => (
            <RowCard key={row.id} title={row.name ?? `Portfolio ${row.id}`} row={row} />
          ))}
        </>
      )}
    </div>
  );
}
