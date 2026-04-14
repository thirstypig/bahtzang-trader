"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { SnapshotData } from "@/lib/api";

interface Props {
  snapshots: SnapshotData[];
}

export default function ReturnDistributionChart({ snapshots }: Props) {
  if (snapshots.length < 5) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
        <p className="text-sm text-zinc-500">
          Need at least 5 snapshots for distribution ({snapshots.length}/5)
        </p>
      </div>
    );
  }

  // Compute daily returns
  const returns: number[] = [];
  for (let i = 1; i < snapshots.length; i++) {
    const prev = snapshots[i - 1].total_equity;
    const curr = snapshots[i].total_equity;
    if (prev > 0) {
      returns.push(((curr / prev) - 1) * 100);
    }
  }

  // Bucket into histogram bins
  const binWidth = 0.5; // 0.5% bins
  const minReturn = Math.floor(Math.min(...returns) / binWidth) * binWidth;
  const maxReturn = Math.ceil(Math.max(...returns) / binWidth) * binWidth;

  const bins: { range: string; count: number; midpoint: number }[] = [];
  for (let lo = minReturn; lo < maxReturn; lo += binWidth) {
    const hi = lo + binWidth;
    const count = returns.filter((r) => r >= lo && r < hi).length;
    bins.push({
      range: `${lo >= 0 ? "+" : ""}${lo.toFixed(1)}%`,
      count,
      midpoint: lo + binWidth / 2,
    });
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h3 className="mb-4 text-sm font-semibold text-white">Daily Return Distribution</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={bins}>
          <XAxis
            dataKey="range"
            tick={{ fill: "#71717a", fontSize: 9 }}
            axisLine={{ stroke: "#3f3f46" }}
            tickLine={false}
            interval={Math.max(0, Math.floor(bins.length / 8))}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value) => [Number(value), "Days"]}
          />
          <ReferenceLine x={bins.findIndex((b) => b.midpoint >= 0) >= 0 ? bins[bins.findIndex((b) => b.midpoint >= 0)]?.range : undefined} stroke="#3f3f46" strokeDasharray="3 3" />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {bins.map((bin, i) => (
              <Cell
                key={i}
                fill={bin.midpoint >= 0 ? "#10b981" : "#ef4444"}
                fillOpacity={0.7}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
