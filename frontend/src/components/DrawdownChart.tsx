"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { SnapshotData } from "@/lib/api";

interface Props {
  snapshots: SnapshotData[];
}

export default function DrawdownChart({ snapshots }: Props) {
  if (snapshots.length < 2) {
    return (
      <div className="flex h-48 items-center justify-center bz-glass">
        <p className="text-sm text-muted">
          Need at least 2 snapshots for drawdown chart ({snapshots.length}/2)
        </p>
      </div>
    );
  }

  let peak = snapshots[0].total_equity;
  const data = snapshots.map((s) => {
    if (s.total_equity > peak) peak = s.total_equity;
    const drawdown = ((s.total_equity - peak) / peak) * 100;
    return {
      date: s.date.slice(5),
      drawdown: +drawdown.toFixed(2),
    };
  });

  return (
    <div className="bz-glass p-5">
      <h3 className="mb-4 text-sm font-semibold text-primary">Drawdown</h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="drawdownGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="rgb(var(--neg))" stopOpacity={0.4} />
              <stop offset="95%" stopColor="rgb(var(--neg))" stopOpacity={0} />
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
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "rgb(var(--card))",
              border: "1px solid rgb(var(--border-strong) / 0.35)",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value) => [`${Number(value).toFixed(2)}%`, "Drawdown"]}
          />
          <ReferenceLine y={0} stroke="rgb(var(--border-strong) / 0.35)" />
          <Area
            dataKey="drawdown"
            stroke="rgb(var(--neg))"
            fill="url(#drawdownGrad)"
            type="monotone"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
