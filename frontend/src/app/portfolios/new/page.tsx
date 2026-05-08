"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createPortfolio } from "@/lib/api";
import type { TradingGoal } from "@/lib/types";

const GOALS = [
  { value: "maximize_returns", label: "Maximize Returns" },
  { value: "steady_income", label: "Steady Income" },
  { value: "capital_preservation", label: "Capital Preservation" },
  { value: "beat_sp500", label: "Beat S&P 500" },
  { value: "swing_trading", label: "Swing Trading" },
  { value: "passive_index", label: "Passive Index" },
];

const RISKS = [
  { value: "conservative", label: "Conservative (Low Risk)" },
  { value: "moderate", label: "Moderate (Balanced)" },
  { value: "aggressive", label: "Aggressive (High Risk)" },
];

const FREQS = [
  { value: "1x", label: "Once Daily" },
  { value: "3x", label: "Three Times Daily" },
  { value: "5x", label: "Five Times Daily" },
];

export default function NewPortfolioPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");
  const [goal, setGoal] = useState("maximize_returns");
  const [risk, setRisk] = useState("moderate");
  const [freq, setFreq] = useState("1x");
  const [targetAmt, setTargetAmt] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);

      if (!name.trim()) {
        setError("Portfolio name is required");
        return;
      }

      const budgetNum = parseFloat(budget);
      if (!budget || isNaN(budgetNum) || budgetNum <= 0) {
        setError("Budget must be a positive number");
        return;
      }

      const portfolio = await createPortfolio({
        name: name.trim(),
        budget: budgetNum,
        trading_goal: goal as TradingGoal,
        risk_profile: risk as "conservative" | "moderate" | "aggressive",
        trading_frequency: freq as "1x" | "3x" | "5x",
        target_amount: targetAmt ? parseFloat(targetAmt) : undefined,
        target_date: targetDate || undefined,
      });

      router.push(`/portfolios/${portfolio.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create portfolio");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-8">
        <Link
          href="/portfolios"
          className="text-accent hover:underline text-sm mb-4 inline-block"
        >
          ← Back to Portfolios
        </Link>
        <h1 className="text-3xl font-bold">Create New Portfolio</h1>
        <p className="text-muted mt-2">
          Set up a new portfolio slice with its own budget and trading rules
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-card rounded-lg p-6 space-y-6">
        {error && (
          <div className="p-4 bg-red-100 text-red-800 rounded-lg">{error}</div>
        )}

        <div>
          <label className="block text-sm font-medium mb-2">
            Portfolio Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Growth Fund, Income Portfolio"
            className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Budget ($)</label>
          <input
            type="number"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            placeholder="10000"
            className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            Trading Goal
          </label>
          <select
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {GOALS.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            Risk Profile
          </label>
          <select
            value={risk}
            onChange={(e) => setRisk(e.target.value)}
            className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {RISKS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            Trading Frequency
          </label>
          <select
            value={freq}
            onChange={(e) => setFreq(e.target.value)}
            className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {FREQS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        <div className="border-t border-border pt-6">
          <h3 className="font-semibold mb-4">Optional: Target Goals</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Target Amount ($)
              </label>
              <input
                type="number"
                value={targetAmt}
                onChange={(e) => setTargetAmt(e.target.value)}
                placeholder="50000"
                className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Target Date (YYYY-MM-DD)
              </label>
              <input
                type="text"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                placeholder="2026-12-31"
                className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
          </div>
        </div>

        <div className="flex gap-4 pt-6">
          <button
            type="submit"
            disabled={saving}
            className="flex-1 px-4 py-3 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 font-medium"
          >
            {saving ? "Creating..." : "Create Portfolio"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/portfolios")}
            className="flex-1 px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors font-medium"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
