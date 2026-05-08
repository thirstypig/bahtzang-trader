"use client";

import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getPortfolioSnapshots } from "@/lib/api";
import { PlanSnapshotData } from "@/lib/types";

interface Props {
  portfolioId: number;
}

export default function PortfolioEquityCurve({ portfolioId }: Props) {
  const [snapshots, setSnapshots] = useState<PlanSnapshotData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPortfolioSnapshots(portfolioId, 90)
      .then((d) => {
        if (!cancelled) setSnapshots(d);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load equity curve");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center bz-glass">
        <p className="text-sm text-muted">Loading equity curve...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-neg/30 bg-neg/10 p-6 text-center">
        <p className="text-sm text-neg">Failed to load equity curve: {error}</p>
      </div>
    );
  }

  if (snapshots.length < 2) {
    return (
      <div className="flex h-64 items-center justify-center bz-glass">
        <p className="text-sm text-muted">
          Need at least 2 snapshots for equity curve ({snapshots.length}/2)
        </p>
      </div>
    );
  }

  const data = snapshots.map((s) => ({
    date: s.date.slice(5), // "MM-DD"
    total_value: s.total_value,
  }));

  return (
    <div className="bz-glass p-5">
      <h3 className="mb-4 text-sm font-semibold text-primary">
        Portfolio Equity Curve
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`portfolioEquityGrad-${portfolioId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgb(var(--pos))" stopOpacity={0.3} />
              <stop offset="100%" stopColor="rgb(var(--pos))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }}
            axisLine={{ stroke: "rgb(var(--border-strong) / 0.35)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) =>
              `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "rgb(var(--card))",
              border: "1px solid rgb(var(--border-strong) / 0.35)",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value) => [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Area
            dataKey="total_value"
            name="Total Value"
            stroke="rgb(var(--pos))"
            strokeWidth={2}
            fill={`url(#portfolioEquityGrad-${portfolioId})`}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
