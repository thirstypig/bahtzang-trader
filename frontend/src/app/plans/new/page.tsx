"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createPlan } from "@/lib/api";
import { TradingGoal } from "@/lib/types";
import Tip from "@/components/Tip";

const GOALS: { id: TradingGoal; label: string; icon: string; desc: string; returns: string }[] = [
  { id: "maximize_returns", label: "Maximize Returns", icon: "📈", desc: "Aggressive growth via momentum", returns: "15-30%/yr" },
  { id: "steady_income", label: "Steady Income", icon: "💰", desc: "Dividends and yield", returns: "4-8%/yr" },
  { id: "capital_preservation", label: "Capital Preservation", icon: "🏦", desc: "Protect principal", returns: "2-4%/yr" },
  { id: "beat_sp500", label: "Beat S&P 500", icon: "🏆", desc: "Sector rotation", returns: "12-18%/yr" },
  { id: "swing_trading", label: "Swing Trading", icon: "⚡", desc: "2-7 day holds", returns: "20-40%/yr" },
  { id: "passive_index", label: "Passive Index", icon: "🌊", desc: "Buy and hold ETFs", returns: "8-12%/yr" },
];

const RISKS: { id: "conservative" | "moderate" | "aggressive"; label: string; icon: string }[] = [
  { id: "conservative", label: "Conservative", icon: "🛡️" },
  { id: "moderate", label: "Moderate", icon: "⚖️" },
  { id: "aggressive", label: "Aggressive", icon: "🔥" },
];

const FREQS: { id: "1x" | "3x" | "5x"; label: string }[] = [
  { id: "1x", label: "1x/day" },
  { id: "3x", label: "3x/day" },
  { id: "5x", label: "5x/day" },
];

export default function NewPlanPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");
  const [goal, setGoal] = useState<TradingGoal>("maximize_returns");
  const [risk, setRisk] = useState<"conservative" | "moderate" | "aggressive">("moderate");
  const [freq, setFreq] = useState<"1x" | "3x" | "5x">("1x");
  const [targetAmt, setTargetAmt] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !budget) return;
    setSaving(true);
    setError(null);
    try {
      const plan = await createPlan({
        name: name.trim(),
        budget: Number(budget),
        trading_goal: goal,
        risk_profile: risk,
        trading_frequency: freq,
        target_amount: targetAmt ? Number(targetAmt) : null,
        target_date: targetDate || null,
      });
      router.push(`/plans/${plan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create plan");
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-primary">Create Investment Plan</h1>
        <p className="mt-1 text-sm text-muted">
          Set up a new portfolio slice with its own budget and strategy
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Name + Budget */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="text-lg font-semibold text-primary">Basics</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-secondary">Plan Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Growth Slice"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2.5 text-sm text-primary placeholder-muted focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="flex items-center gap-1 text-sm font-medium text-secondary">
                Budget
                <Tip text="How much money to allocate to this plan. The total across all plans can't exceed your Alpaca account value." />
              </label>
              <div className="relative mt-1.5">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">$</span>
                <input
                  type="number"
                  required
                  min="1"
                  step="0.01"
                  placeholder="100"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-card-alt py-2.5 pl-7 pr-3 text-sm text-primary placeholder-muted focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Trading Goal */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="text-lg font-semibold text-primary">Trading Goal</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {GOALS.map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => setGoal(g.id)}
                className={`rounded-xl border p-4 text-left transition-all ${
                  goal === g.id
                    ? "border-emerald-500 bg-emerald-900/30 ring-1 ring-emerald-500"
                    : "border-border bg-surface hover:border-border-strong"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span>{g.icon}</span>
                  <span className="text-sm font-semibold text-primary">{g.label}</span>
                </div>
                <p className="mt-1 text-xs text-secondary">{g.desc}</p>
                <p className="mt-2 text-[10px] text-accent">{g.returns}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Risk + Frequency */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h2 className="text-lg font-semibold text-primary">Risk Profile</h2>
              <div className="mt-4 space-y-2">
                {RISKS.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setRisk(r.id)}
                    className={`flex w-full items-center gap-2 rounded-lg border px-4 py-3 text-left text-sm transition-all ${
                      risk === r.id
                        ? "border-emerald-500 bg-emerald-900/30"
                        : "border-border bg-surface hover:border-border-strong"
                    }`}
                  >
                    <span>{r.icon}</span>
                    <span className="font-medium text-primary">{r.label}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-primary">Frequency</h2>
              <div className="mt-4 space-y-2">
                {FREQS.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFreq(f.id)}
                    className={`w-full rounded-lg border px-4 py-3 text-left text-sm font-medium transition-all ${
                      freq === f.id
                        ? "border-blue-500 bg-blue-900/30 text-primary"
                        : "border-border bg-surface text-secondary hover:border-border-strong"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Timeline Goal (optional) */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="text-lg font-semibold text-primary">Timeline Goal (optional)</h2>
          <p className="mt-1 text-sm text-muted">Set a target for the AI to work towards</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-secondary">Target Amount</label>
              <div className="relative mt-1.5">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">$</span>
                <input
                  type="number"
                  min="1"
                  placeholder="500"
                  value={targetAmt}
                  onChange={(e) => setTargetAmt(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-card-alt py-2.5 pl-7 pr-3 text-sm text-primary placeholder-muted focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-secondary">Target Date</label>
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2.5 text-sm text-primary focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={saving || !name.trim() || !budget}
            className="rounded-lg bg-emerald-600 px-8 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
          >
            {saving ? "Creating..." : "Create Plan"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/plans")}
            className="text-sm text-secondary transition-colors hover:text-primary"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
