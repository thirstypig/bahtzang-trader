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
      <div className="flex h-64 items-center justify-center bz-glass p-6">
        <p className="text-sm text-muted">No trade history to chart</p>
      </div>
    );
  }

  return (
    <div className="bz-glass p-6">
      <h2 className="text-sm font-medium text-secondary">
        Portfolio Value Over Time
      </h2>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="valueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="rgb(var(--pos))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="rgb(var(--pos))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border-strong) / 0.25)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
              axisLine={{ stroke: "rgb(var(--border-strong) / 0.35)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
              axisLine={{ stroke: "rgb(var(--border-strong) / 0.35)" }}
              tickLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgb(var(--card))",
                border: "1px solid rgb(var(--border-strong) / 0.35)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value) => [formatCurrency(Number(value)), "Value"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="rgb(var(--pos))"
              strokeWidth={2}
              fill="url(#valueGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
