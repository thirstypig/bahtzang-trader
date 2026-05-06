"use client";

import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Balance, Position } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

interface AllocationChartProps {
  positions: Position[];
  balance: Balance | null;
}

const COLORS = [
  "rgb(var(--pos))",
  "#3b82f6",
  "#f59e0b",
  "rgb(var(--neg))",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
];

export default function AllocationChart({
  positions,
  balance,
}: AllocationChartProps) {
  const data = positions.map((p) => ({
    name: p.instrument?.symbol || "Unknown",
    value: p.marketValue || 0,
  }));

  if (balance && balance.cash_available > 0) {
    data.push({ name: "Cash", value: balance.cash_available });
  }

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center bz-glass p-6">
        <p className="text-sm text-muted">No positions to chart</p>
      </div>
    );
  }

  return (
    <div className="bz-glass p-6">
      <h2 className="text-sm font-medium text-secondary">
        Portfolio Allocation
      </h2>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((_, i) => (
                <Cell
                  key={`cell-${i}`}
                  fill={COLORS[i % COLORS.length]}
                  stroke="transparent"
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "rgb(var(--card))",
                border: "1px solid rgb(var(--border-strong) / 0.35)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value) => formatCurrency(Number(value))}
            />
            <Legend
              wrapperStyle={{ fontSize: "12px", color: "rgb(var(--text-secondary))" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
