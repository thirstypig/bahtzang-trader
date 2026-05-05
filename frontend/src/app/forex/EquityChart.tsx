"use client";

import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  data: { date: string; equity: number }[];
  initial: number;
}

export default function ForexEquityChart({ data, initial }: Props) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <XAxis
          dataKey="date"
          stroke="currentColor"
          className="text-muted"
          tick={{ fontSize: 11 }}
          minTickGap={48}
        />
        <YAxis
          stroke="currentColor"
          className="text-muted"
          tick={{ fontSize: 11 }}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => `$${Math.round(v / 100) * 100}`}
        />
        <Tooltip
          contentStyle={{
            background: "rgb(24,24,27)",
            border: "1px solid rgb(63,63,70)",
            borderRadius: 6,
            fontSize: 12,
          }}
          formatter={(v) => [`$${Number(v).toFixed(2)}`, "equity"]}
        />
        <ReferenceLine y={initial} stroke="rgb(113,113,122)" strokeDasharray="4 4" />
        <Line
          type="monotone"
          dataKey="equity"
          stroke="rgb(16,185,129)"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
