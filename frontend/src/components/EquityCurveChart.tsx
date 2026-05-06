"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { SnapshotData } from "@/lib/api";

interface Props {
  snapshots: SnapshotData[];
}

export default function EquityCurveChart({ snapshots }: Props) {
  if (snapshots.length < 2) {
    return (
      <div className="flex h-64 items-center justify-center bz-glass">
        <p className="text-sm text-muted">
          Need at least 2 snapshots for equity curve ({snapshots.length}/2)
        </p>
      </div>
    );
  }

  const firstEquity = snapshots[0].total_equity;
  const firstSpy = snapshots[0].spy_close;

  const data = snapshots.map((s) => ({
    date: s.date.slice(5), // "MM-DD"
    portfolio: +((s.total_equity / firstEquity - 1) * 100).toFixed(2),
    spy: firstSpy && s.spy_close
      ? +((s.spy_close / firstSpy - 1) * 100).toFixed(2)
      : null,
  }));

  return (
    <div className="bz-glass p-5">
      <h3 className="mb-4 text-sm font-semibold text-primary">Equity Curve vs SPY</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
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
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "rgb(var(--card))",
              border: "1px solid rgb(var(--border-strong) / 0.35)",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value) => [`${Number(value).toFixed(2)}%`]}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "rgb(var(--text-secondary))" }}
          />
          <Line
            dataKey="portfolio"
            name="Portfolio"
            stroke="rgb(var(--pos))"
            strokeWidth={2}
            dot={false}
          />
          <Line
            dataKey="spy"
            name="SPY"
            stroke="rgb(var(--text-secondary))"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
