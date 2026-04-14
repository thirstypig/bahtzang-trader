"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Trade } from "@/lib/types";
import { formatCurrency, getTimezone } from "@/lib/utils";

interface ValueChartProps {
  trades: Trade[];
}

export default function ValueChart({ trades }: ValueChartProps) {
  // Build cumulative portfolio value from executed trades
  // Most recent trades come first from the API, so reverse for chronological order
  const sorted = [...trades]
    .filter((t) => t.executed && t.price)
    .reverse();

  let cumulative = 0;
  const data = sorted.map((t) => {
    const value = (t.price || 0) * t.quantity;
    if (t.action === "buy") cumulative += value;
    if (t.action === "sell") cumulative -= value;
    return {
      date: new Date(t.timestamp).toLocaleDateString("en-US", {
        timeZone: getTimezone(),
        month: "short",
        day: "numeric",
      }),
      value: Math.abs(cumulative),
    };
  });

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <p className="text-sm text-zinc-500">No trade history to chart</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
      <h2 className="text-sm font-medium text-zinc-400">
        Portfolio Value Over Time
      </h2>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="valueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "#71717a" }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#71717a" }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value) => [formatCurrency(Number(value)), "Value"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#valueGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
