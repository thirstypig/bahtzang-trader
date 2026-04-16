"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { InvestmentPlan } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

interface Props {
  plans: InvestmentPlan[];
  onSliceClick?: (planId: number) => void;
}

const COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

export default function PlanAllocationChart({ plans, onSliceClick }: Props) {
  if (plans.length === 0) return null;

  const totalBudget = plans.reduce((s, p) => s + p.budget, 0);
  const data = plans.map((p, i) => ({
    name: p.name,
    value: p.budget,
    pct: totalBudget > 0 ? ((p.budget / totalBudget) * 100).toFixed(1) : "0",
    planId: p.id,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-primary">Budget Allocation</h3>
      <div className="flex items-center gap-6">
        <div className="relative h-48 w-48 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                dataKey="value"
                onClick={(_, index) => onSliceClick?.(data[index].planId)}
                style={{ cursor: onSliceClick ? "pointer" : "default" }}
              >
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #3f3f46",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value) => [`${formatCurrency(Number(value))}`]}
              />
            </PieChart>
          </ResponsiveContainer>
          {/* Center label */}
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <p className="text-lg font-bold text-primary">{formatCurrency(totalBudget)}</p>
            <p className="text-[10px] text-muted">Total</p>
          </div>
        </div>

        {/* Legend */}
        <div className="space-y-2">
          {data.map((entry) => (
            <button
              key={entry.planId}
              onClick={() => onSliceClick?.(entry.planId)}
              className="flex items-center gap-2 text-left transition-colors hover:text-primary"
            >
              <div className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: entry.color }} />
              <div>
                <p className="text-xs font-medium text-secondary">{entry.name}</p>
                <p className="text-[10px] text-muted">
                  {formatCurrency(entry.value)} ({entry.pct}%)
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
