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
  "#10b981",
  "#3b82f6",
  "#f59e0b",
  "#ef4444",
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
      <div className="flex h-64 items-center justify-center rounded-xl border border-border bg-card p-6">
        <p className="text-sm text-muted">No positions to chart</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-6">
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
                backgroundColor: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value) => formatCurrency(Number(value))}
            />
            <Legend
              wrapperStyle={{ fontSize: "12px", color: "#a1a1aa" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
