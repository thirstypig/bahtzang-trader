"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createPortfolio } from "@/lib/api";
import type { TradingGoal } from "@/lib/types";

// ---------------------------------------------------------------------------
// Metadata for each selector
// ---------------------------------------------------------------------------

const GOALS = [
  {
    value: "maximize_returns",
    label: "Maximize Returns",
    icon: "📈",
    description: "Prioritize capital growth — higher volatility accepted for higher upside",
  },
  {
    value: "steady_income",
    label: "Steady Income",
    icon: "💰",
    description: "Focus on dividend-paying stocks and consistent, recurring yield",
  },
  {
    value: "capital_preservation",
    label: "Capital Preservation",
    icon: "🏦",
    description: "Protect principal first — minimize losses over maximizing gains",
  },
  {
    value: "beat_sp500",
    label: "Beat S&P 500",
    icon: "🏆",
    description: "Outperform the benchmark index over the full investment period",
  },
  {
    value: "swing_trading",
    label: "Swing Trading",
    icon: "⚡",
    description: "Hold positions days to weeks, capturing short-term price moves",
  },
  {
    value: "passive_index",
    label: "Passive Index",
    icon: "🌊",
    description: "Track broad market indices with minimal active decision-making",
  },
];

const RISKS = [
  {
    value: "conservative",
    label: "Conservative",
    sublabel: "Low Risk",
    icon: "🛡️",
    description: "Tight stop-losses, bonds & blue-chips, max 10% per position",
    expectedCagr: 0.08,
  },
  {
    value: "moderate",
    label: "Moderate",
    sublabel: "Balanced",
    icon: "⚖️",
    description: "Diversified across sectors — balanced growth and downside protection",
    expectedCagr: 0.14,
  },
  {
    value: "aggressive",
    label: "Aggressive",
    sublabel: "High Risk",
    icon: "🚀",
    description: "Higher concentration, growth & momentum names, accepts large drawdowns",
    expectedCagr: 0.24,
  },
];

const FREQS = [
  {
    value: "1x",
    label: "Once Daily",
    sublabel: "9:35 AM ET",
    icon: "🌅",
    description: "One decision per day — lowest churn, clearest signals",
    multiplier: 1.0,
  },
  {
    value: "3x",
    label: "Three Daily",
    sublabel: "Morning · Mid · Close",
    icon: "⚡",
    description: "Morning, midday, and afternoon trading sessions",
    multiplier: 1.05,
  },
  {
    value: "5x",
    label: "Five Daily",
    sublabel: "Most Active",
    icon: "🔥",
    description: "Five intraday windows — most responsive to market moves",
    multiplier: 1.1,
  },
];

// ---------------------------------------------------------------------------
// Goal / risk alignment matrix
// ---------------------------------------------------------------------------

type Alignment = "great" | "ok" | "poor";

const ALIGNMENT: Record<string, Record<string, Alignment>> = {
  maximize_returns:     { conservative: "poor",  moderate: "ok",    aggressive: "great" },
  steady_income:        { conservative: "great", moderate: "ok",    aggressive: "poor"  },
  capital_preservation: { conservative: "great", moderate: "ok",    aggressive: "poor"  },
  beat_sp500:           { conservative: "poor",  moderate: "great", aggressive: "great" },
  swing_trading:        { conservative: "poor",  moderate: "ok",    aggressive: "great" },
  passive_index:        { conservative: "great", moderate: "great", aggressive: "ok"    },
};

// ---------------------------------------------------------------------------
// Success score computation (pure, no side effects)
// ---------------------------------------------------------------------------

interface Factor {
  label: string;
  status: "good" | "warn" | "bad" | "info";
}

interface ScoreResult {
  score: number;
  label: string;
  color: string;
  barColor: string;
  requiredCagr: number | null;
  expectedCagr: number;
  years: number | null;
  alignment: Alignment;
  factors: Factor[];
  suggestions: string[];
  hasTarget: boolean;
}

function computeScore(
  budget: number,
  targetAmt: number,
  targetDate: string,
  risk: string,
  freq: string,
  goal: string,
): ScoreResult {
  const riskMeta = RISKS.find((r) => r.value === risk)!;
  const freqMeta = FREQS.find((f) => f.value === freq)!;
  const alignment: Alignment = ALIGNMENT[goal]?.[risk] ?? "ok";
  const expectedCagr = riskMeta.expectedCagr * freqMeta.multiplier;
  const hasTarget = targetAmt > 0 && !!targetDate;

  const scoreLabel = (s: number) =>
    s >= 75 ? "Strong" : s >= 55 ? "Good" : s >= 35 ? "Moderate" : "Low";
  const scoreColor = (s: number) =>
    s >= 75 ? "text-pos" : s >= 55 ? "text-yellow-400" : s >= 35 ? "text-yellow-500" : "text-neg";
  const barColor = (s: number) =>
    s >= 75 ? "bg-pos" : s >= 55 ? "bg-yellow-400" : s >= 35 ? "bg-yellow-500" : "bg-neg";

  const alignFactor: Factor = {
    label:
      alignment === "great"
        ? "Goal & risk well-aligned"
        : alignment === "ok"
        ? "Goal & risk compatible"
        : "Goal & risk misaligned",
    status: alignment === "great" ? "good" : alignment === "ok" ? "info" : "warn",
  };

  if (!hasTarget) {
    const base = alignment === "great" ? 70 : alignment === "ok" ? 55 : 35;
    return {
      score: base,
      label: scoreLabel(base),
      color: scoreColor(base),
      barColor: barColor(base),
      requiredCagr: null,
      expectedCagr,
      years: null,
      alignment,
      hasTarget: false,
      factors: [alignFactor, { label: `~${(expectedCagr * 100).toFixed(0)}% expected annual return`, status: "info" }],
      suggestions:
        alignment === "poor"
          ? ["Goal and risk profile are misaligned — consider adjusting one to match the other"]
          : [],
    };
  }

  const today = new Date();
  const deadline = new Date(targetDate);
  const years = (deadline.getTime() - today.getTime()) / (365.25 * 24 * 60 * 60 * 1000);

  if (years <= 0) {
    return {
      score: 5,
      label: "Low",
      color: "text-neg",
      barColor: "bg-neg",
      requiredCagr: null,
      expectedCagr,
      years: 0,
      alignment,
      hasTarget: true,
      factors: [{ label: "Target date is in the past", status: "bad" }],
      suggestions: ["Update target date to a future date"],
    };
  }

  const requiredCagr = Math.pow(targetAmt / budget, 1 / years) - 1;

  if (requiredCagr <= 0) {
    return {
      score: 98,
      label: "Strong",
      color: "text-pos",
      barColor: "bg-pos",
      requiredCagr: 0,
      expectedCagr,
      years,
      alignment,
      hasTarget: true,
      factors: [
        { label: "Budget already meets or exceeds target", status: "good" },
        { label: `${years.toFixed(1)}yr runway`, status: "good" },
        alignFactor,
      ],
      suggestions: [],
    };
  }

  const ratio = expectedCagr / requiredCagr;
  const alignBonus = alignment === "great" ? 5 : alignment === "poor" ? -8 : 0;
  const timeBonus = years >= 3 ? 5 : years < 0.5 ? -10 : 0;

  // Smooth sigmoid: ratio=0.7 → ~50%, ratio=1 → ~74%, ratio=1.5 → ~92%
  const raw = 50 + 45 * Math.tanh((ratio - 0.7) * 2) + alignBonus + timeBonus;
  const score = Math.round(Math.min(95, Math.max(5, raw)));

  // Suggestions when below 70%
  const suggestions: string[] = [];
  if (score < 70) {
    const achievableTarget = Math.round(budget * Math.pow(1 + expectedCagr, years));
    if (achievableTarget < targetAmt && achievableTarget > budget) {
      suggestions.push(
        `Lower target to $${achievableTarget.toLocaleString()} to reach ~70%+ likelihood`
      );
    }
    const yearsNeeded = Math.log(targetAmt / budget) / Math.log(1 + expectedCagr * 1.3);
    if (yearsNeeded > years + 0.5 && yearsNeeded < 30) {
      const extYear = new Date(today);
      extYear.setFullYear(today.getFullYear() + Math.ceil(yearsNeeded));
      suggestions.push(`Extend deadline to ${extYear.getFullYear()} for ~70%+ likelihood`);
    }
    if (alignment === "poor") {
      suggestions.push("Align your goal and risk profile for a stronger match");
    }
  }

  const factors: Factor[] = [
    {
      label: `${(requiredCagr * 100).toFixed(1)}% CAGR needed`,
      status: ratio >= 1.2 ? "good" : ratio >= 0.8 ? "warn" : "bad",
    },
    {
      label: `${years.toFixed(1)}yr runway`,
      status: years >= 2 ? "good" : years >= 1 ? "warn" : "bad",
    },
    alignFactor,
    { label: `~${(expectedCagr * 100).toFixed(0)}% expected annual`, status: "info" },
  ];

  return {
    score,
    label: scoreLabel(score),
    color: scoreColor(score),
    barColor: barColor(score),
    requiredCagr,
    expectedCagr,
    years,
    alignment,
    hasTarget: true,
    factors,
    suggestions,
  };
}

// ---------------------------------------------------------------------------
// SelectCard
// ---------------------------------------------------------------------------

function SelectCard({
  icon,
  label,
  sublabel,
  description,
  selected,
  onClick,
}: {
  icon: string;
  label: string;
  sublabel?: string;
  description: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "text-left p-4 rounded-xl border transition-all duration-150 w-full",
        selected
          ? "border-accent bg-accent/10 ring-1 ring-accent"
          : "border-border bz-glass-soft hover:border-accent/50",
      ].join(" ")}
    >
      <div className="text-2xl mb-2">{icon}</div>
      <div className="font-semibold text-sm">{label}</div>
      {sublabel && (
        <div className="text-xs text-muted mb-1">{sublabel}</div>
      )}
      <div className="text-xs text-muted leading-snug mt-1">{description}</div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// SuccessPanel
// ---------------------------------------------------------------------------

const FACTOR_ICON: Record<Factor["status"], string> = {
  good: "✅",
  warn: "⚠️",
  bad: "❌",
  info: "ℹ️",
};

function SuccessPanel({ result }: { result: ScoreResult }) {
  return (
    <div className="bz-glass rounded-xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-sm text-muted uppercase tracking-wide">
            Success Likelihood
          </h3>
          {!result.hasTarget && (
            <p className="text-xs text-muted mt-0.5">
              Set a target amount &amp; date for full analysis
            </p>
          )}
        </div>
        <div className="text-right">
          <span className={`text-4xl font-bold tabular-nums ${result.color}`}>
            {result.score}%
          </span>
          <div className={`text-xs font-medium mt-0.5 ${result.color}`}>{result.label}</div>
        </div>
      </div>

      {/* Score bar */}
      <div className="h-2.5 rounded-full bg-border/40 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${result.barColor}`}
          style={{ width: `${result.score}%` }}
        />
      </div>

      {/* Factor chips */}
      <div className="flex flex-wrap gap-2">
        {result.factors.map((f, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-card border border-border"
          >
            <span>{FACTOR_ICON[f.status]}</span>
            <span
              className={
                f.status === "good"
                  ? "text-pos"
                  : f.status === "bad"
                  ? "text-neg"
                  : f.status === "warn"
                  ? "text-yellow-500"
                  : "text-muted"
              }
            >
              {f.label}
            </span>
          </span>
        ))}
      </div>

      {/* Suggestions */}
      {result.suggestions.length > 0 && (
        <div className="border-t border-border pt-3 space-y-1">
          {result.suggestions.map((s, i) => (
            <p key={i} className="text-xs text-muted">
              💡 {s}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

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

  const scoreResult = useMemo(() => {
    const budgetNum = parseFloat(budget) || 0;
    const targetNum = parseFloat(targetAmt) || 0;
    return computeScore(budgetNum, targetNum, targetDate, risk, freq, goal);
  }, [budget, targetAmt, targetDate, risk, freq, goal]);

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
    <div className="p-6 md:p-8 max-w-3xl">
      <div className="mb-8">
        <Link href="/portfolios" className="text-accent hover:underline text-sm mb-4 inline-block">
          ← Back to Portfolios
        </Link>
        <h1 className="text-3xl font-bold">Create New Portfolio</h1>
        <p className="text-muted mt-2">
          Set up a new portfolio slice with its own budget, goal, and trading rules
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {error && (
          <div className="p-4 bg-neg/10 text-neg border border-neg/30 rounded-xl">{error}</div>
        )}

        {/* Name + Budget */}
        <div className="bz-glass rounded-xl p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Portfolio Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Growth Fund, Income Portfolio"
              className="w-full px-4 py-2.5 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Budget ($)</label>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="10000"
              min="1"
              className="w-full px-4 py-2.5 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        </div>

        {/* Trading Goal */}
        <div>
          <h2 className="text-base font-semibold mb-1">Trading Goal</h2>
          <p className="text-xs text-muted mb-3">What outcome are you optimizing for?</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {GOALS.map((g) => (
              <SelectCard
                key={g.value}
                icon={g.icon}
                label={g.label}
                description={g.description}
                selected={goal === g.value}
                onClick={() => setGoal(g.value)}
              />
            ))}
          </div>
        </div>

        {/* Risk Profile */}
        <div>
          <h2 className="text-base font-semibold mb-1">Risk Profile</h2>
          <p className="text-xs text-muted mb-3">How much drawdown are you willing to accept?</p>
          <div className="grid grid-cols-3 gap-3">
            {RISKS.map((r) => (
              <SelectCard
                key={r.value}
                icon={r.icon}
                label={r.label}
                sublabel={r.sublabel}
                description={r.description}
                selected={risk === r.value}
                onClick={() => setRisk(r.value)}
              />
            ))}
          </div>
        </div>

        {/* Trading Frequency */}
        <div>
          <h2 className="text-base font-semibold mb-1">Trading Frequency</h2>
          <p className="text-xs text-muted mb-3">How many times per day should Claude decide?</p>
          <div className="grid grid-cols-3 gap-3">
            {FREQS.map((f) => (
              <SelectCard
                key={f.value}
                icon={f.icon}
                label={f.label}
                sublabel={f.sublabel}
                description={f.description}
                selected={freq === f.value}
                onClick={() => setFreq(f.value)}
              />
            ))}
          </div>
        </div>

        {/* Target Goals */}
        <div>
          <h2 className="text-base font-semibold mb-1">Target Goal <span className="text-muted font-normal text-sm">(optional)</span></h2>
          <p className="text-xs text-muted mb-3">Set a dollar target and deadline to unlock success analysis</p>
          <div className="bz-glass-soft rounded-xl p-5 grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Target Amount ($)</label>
              <input
                type="number"
                value={targetAmt}
                onChange={(e) => setTargetAmt(e.target.value)}
                placeholder="50000"
                min="1"
                className="w-full px-4 py-2.5 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Target Date</label>
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="w-full px-4 py-2.5 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
          </div>
        </div>

        {/* Success Likelihood Panel */}
        <SuccessPanel result={scoreResult} />

        {/* Actions */}
        <div className="flex gap-4 pb-8">
          <button
            type="submit"
            disabled={saving}
            className="flex-1 px-4 py-3 bg-accent text-white rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 font-medium"
          >
            {saving ? "Creating..." : "Create Portfolio"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/portfolios")}
            className="flex-1 px-4 py-3 border border-border rounded-xl hover:bg-card transition-colors font-medium"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
