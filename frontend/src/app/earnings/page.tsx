"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getEarningsCalendar, refreshEarnings } from "@/lib/api";
import { EarningsEvent } from "@/lib/types";
import Spinner from "@/components/Spinner";
import Tip from "@/components/Tip";

export default function EarningsPage() {
  const { user } = useAuth();
  const [earnings, setEarnings] = useState<EarningsEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (!user) return;
    getEarningsCalendar(30)
      .then((res) => setEarnings(res.earnings))
      .catch(() => setEarnings([]))
      .finally(() => setLoading(false));
  }, [user]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshEarnings();
      const res = await getEarningsCalendar(30);
      setEarnings(res.earnings);
    } finally {
      setRefreshing(false);
    }
  }

  function daysUntil(dateStr: string): number {
    const now = new Date();
    const target = new Date(dateStr + "T00:00:00");
    return Math.ceil(
      (target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
    );
  }

  function proximityColor(days: number) {
    if (days <= 1) return "bg-red-500/10 border-red-500/20 text-red-400";
    if (days <= 3) return "bg-amber-500/10 border-amber-500/20 text-amber-400";
    return "bg-emerald-500/10 border-emerald-500/20 text-emerald-400";
  }

  function proximityBadge(days: number) {
    if (days <= 1) return "bg-red-500/10 text-red-400";
    if (days <= 3) return "bg-amber-500/10 text-amber-400";
    return "bg-zinc-500/10 text-zinc-400";
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  // Group by date
  const grouped = earnings.reduce<Record<string, EarningsEvent[]>>(
    (acc, e) => {
      if (!acc[e.report_date]) acc[e.report_date] = [];
      acc[e.report_date].push(e);
      return acc;
    },
    {}
  );
  const dates = Object.keys(grouped).sort();

  const thisWeek = earnings.filter((e) => daysUntil(e.report_date) <= 7);
  const tomorrow = earnings.filter((e) => daysUntil(e.report_date) <= 1);
  const nearest = earnings.length > 0 ? earnings[0] : null;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white">Earnings Calendar</h1>
            <Tip text="Companies report their financial results (earnings) every quarter. Stock prices often move sharply after earnings — up or down. The bot automatically reduces position sizes near earnings dates to protect you from surprise moves." />
          </div>
          <p className="mt-1 text-sm text-zinc-500">
            Upcoming earnings for held positions — reduces position sizes near
            reporting dates
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 disabled:opacity-50"
        >
          {refreshing ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>

      {/* Summary cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <p className="text-xs text-zinc-500">This Week</p>
          <p className="mt-2 text-3xl font-bold text-white">
            {thisWeek.length}
          </p>
          <p className="mt-1 text-xs text-zinc-600">earnings reports</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <p className="text-xs text-zinc-500">Tomorrow / Today</p>
          <p
            className={`mt-2 text-3xl font-bold ${
              tomorrow.length > 0 ? "text-amber-400" : "text-zinc-400"
            }`}
          >
            {tomorrow.length}
          </p>
          <p className="mt-1 text-xs text-zinc-600">
            {tomorrow.length > 0 ? "position sizes reduced" : "all clear"}
          </p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <p className="text-xs text-zinc-500">Total Tracked</p>
          <p className="mt-2 text-3xl font-bold text-emerald-400">
            {earnings.length}
          </p>
          <p className="mt-1 text-xs text-zinc-600">next 30 days</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <p className="text-xs text-zinc-500">Next Report</p>
          <p className="mt-2 text-3xl font-bold text-white">
            {nearest ? nearest.symbol : "—"}
          </p>
          <p className="mt-1 text-xs text-zinc-600">
            {nearest
              ? `${nearest.report_date} (${daysUntil(nearest.report_date)}d)`
              : "No upcoming earnings"}
          </p>
        </div>
      </div>

      {/* Empty state */}
      {earnings.length === 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-12 text-center">
          <p className="text-sm text-zinc-400">
            No upcoming earnings found. Click &quot;Refresh Data&quot; to fetch
            earnings for your current holdings from Finnhub.
          </p>
          <p className="mt-2 text-xs text-zinc-600">
            Requires FINNHUB_API_KEY to be set in the backend .env file.
          </p>
        </div>
      )}

      {/* Date-grouped list */}
      {dates.map((dateStr) => {
        const days = daysUntil(dateStr);
        const events = grouped[dateStr];
        return (
          <div key={dateStr} className="mb-4">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-sm font-medium text-white">{dateStr}</span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${proximityBadge(days)}`}
              >
                {days === 0
                  ? "Today"
                  : days === 1
                    ? "Tomorrow"
                    : `${days} days`}
              </span>
            </div>
            <div className="space-y-2">
              {events.map((e, i) => (
                <div
                  key={i}
                  className={`flex items-center justify-between rounded-lg border p-4 ${proximityColor(days)}`}
                >
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-bold text-white">
                      {e.symbol}
                    </span>
                    {e.hour && (
                      <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-medium uppercase text-zinc-400">
                        {e.hour === "bmo"
                          ? "Before Open"
                          : e.hour === "amc"
                            ? "After Close"
                            : e.hour}
                      </span>
                    )}
                    {e.fiscal_quarter && (
                      <span className="text-xs text-zinc-500">
                        {e.fiscal_quarter}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-6 text-xs text-zinc-400">
                    {e.eps_estimate !== null && (
                      <span>
                        EPS est:{" "}
                        <span className="text-white">
                          ${e.eps_estimate.toFixed(2)}
                        </span>
                      </span>
                    )}
                    {e.revenue_estimate !== null && (
                      <span>
                        Rev est:{" "}
                        <span className="text-white">
                          $
                          {e.revenue_estimate >= 1_000_000_000
                            ? `${(e.revenue_estimate / 1_000_000_000).toFixed(1)}B`
                            : `${(e.revenue_estimate / 1_000_000).toFixed(0)}M`}
                        </span>
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
