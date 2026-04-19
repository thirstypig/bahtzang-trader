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
import { getPlanSnapshots } from "@/lib/api";
import { PlanSnapshotData } from "@/lib/types";

interface Props {
  planId: number;
}

export default function PlanEquityCurve({ planId }: Props) {
  const [snapshots, setSnapshots] = useState<PlanSnapshotData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPlanSnapshots(planId, 90)
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
  }, [planId]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-border bg-card">
        <p className="text-sm text-muted">Loading equity curve...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-red-800 bg-red-950/30 p-6 text-center">
        <p className="text-sm text-red-400">Failed to load equity curve: {error}</p>
      </div>
    );
  }

  if (snapshots.length < 2) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-border bg-card">
        <p className="text-sm text-muted">
          Need at least 2 snapshots for equity curve ({snapshots.length}/2)
        </p>
      </div>
    );
  }

  const firstValue = snapshots[0].total_value;

  const data = snapshots.map((s) => ({
    date: s.date.slice(5), // "MM-DD"
    total_value: s.total_value,
  }));

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-primary">
        Plan Equity Curve
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`planEquityGrad-${planId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
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
            tickFormatter={(v: number) =>
              `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value) => [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Area
            dataKey="total_value"
            name="Total Value"
            stroke="#10b981"
            strokeWidth={2}
            fill={`url(#planEquityGrad-${planId})`}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
