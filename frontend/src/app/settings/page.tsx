"use client";

import { useEffect, useState } from "react";
import { getGuardrails, triggerRun, updateGuardrails } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Guardrails, TradingGoal } from "@/lib/types";
import KillSwitchButton from "@/components/KillSwitchButton";
import Spinner from "@/components/Spinner";
import ConfirmModal from "@/components/ConfirmModal";

const RISK_PROFILES = [
  {
    id: "conservative" as const,
    label: "Conservative",
    icon: "🛡️",
    description: "Preserve capital. Few trades, high conviction only.",
    details: "30% invested · 3% stop · 75% confidence · 3/day",
    border: "border-emerald-800", bg: "bg-emerald-900/20",
    activeBorder: "border-emerald-500", activeBg: "bg-emerald-900/40", ring: "ring-emerald-500",
  },
  {
    id: "moderate" as const,
    label: "Moderate",
    icon: "⚖️",
    description: "Balanced risk and reward. Steady growth.",
    details: "60% invested · 5% stop · 60% confidence · 5/day",
    border: "border-blue-800", bg: "bg-blue-900/20",
    activeBorder: "border-blue-500", activeBg: "bg-blue-900/40", ring: "ring-blue-500",
  },
  {
    id: "aggressive" as const,
    label: "Aggressive",
    icon: "🔥",
    description: "Maximize returns. More trades, higher risk.",
    details: "90% invested · 8% stop · 45% confidence · 10/day",
    border: "border-amber-800", bg: "bg-amber-900/20",
    activeBorder: "border-amber-500", activeBg: "bg-amber-900/40", ring: "ring-amber-500",
  },
];

const TRADING_GOALS: {
  id: TradingGoal;
  label: string;
  icon: string;
  description: string;
  returns: string;
  frequency: string;
  tickers: string;
}[] = [
  {
    id: "maximize_returns",
    label: "Maximize Returns",
    icon: "📈",
    description: "Aggressive growth through momentum and factor investing",
    returns: "15-30%/yr",
    frequency: "3x/day",
    tickers: "NVDA, AAPL, QQQ, BTC",
  },
  {
    id: "steady_income",
    label: "Steady Income",
    icon: "💰",
    description: "Dividends and covered call premiums for passive income",
    returns: "4-8%/yr",
    frequency: "1x/day",
    tickers: "SCHD, JEPI, O, VYM",
  },
  {
    id: "capital_preservation",
    label: "Capital Preservation",
    icon: "🏦",
    description: "Protect principal with treasuries and low-volatility stocks",
    returns: "2-4%/yr",
    frequency: "1x/day",
    tickers: "SHV, BIL, USMV, XLU",
  },
  {
    id: "beat_sp500",
    label: "Beat S&P 500",
    icon: "🏆",
    description: "Outperform the benchmark through tactical sector rotation",
    returns: "12-18%/yr",
    frequency: "3x/day",
    tickers: "XLK, XLV, XLF, XLE",
  },
  {
    id: "swing_trading",
    label: "Swing Trading",
    icon: "⚡",
    description: "Capture 2-5% moves on technical setups, hold 2-7 days",
    returns: "20-40%/yr",
    frequency: "5x/day",
    tickers: "AAPL, TSLA, AMD, BTC",
  },
  {
    id: "passive_index",
    label: "Passive Index",
    icon: "🌊",
    description: "Buy and hold broad index ETFs. Rebalance quarterly.",
    returns: "8-12%/yr",
    frequency: "1x/week",
    tickers: "VOO, VTI, VXUS",
  },
];

const FREQUENCIES = [
  { id: "1x" as const, label: "1x/day", times: "9:35 AM ET" },
  { id: "3x" as const, label: "3x/day", times: "9:35 AM, 1:00 PM, 3:45 PM ET" },
  { id: "5x" as const, label: "5x/day", times: "9:35, 10:30, 12:00, 1:30, 3:00 ET" },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [guardrails, setGuardrails] = useState<Guardrails | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);

  useEffect(() => {
    if (!user) return;
    getGuardrails()
      .then(setGuardrails)
      .finally(() => setLoading(false));
  }, [user]);

  async function handleUpdate(partial: Partial<Guardrails>) {
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateGuardrails(partial);
      setGuardrails(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSaving(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!guardrails) return;
    await handleUpdate(guardrails);
  }

  async function handleRunBot() {
    setRunning(true);
    setRunResult(null);
    setShowRunModal(false);
    try {
      const result = await triggerRun();
      setRunResult(
        `${result.action.toUpperCase()} ${result.ticker || ""} — ${result.executed ? "Executed" : "Not executed"}${result.guardrail_block_reason ? ` (${result.guardrail_block_reason})` : ""}`
      );
    } catch (err) {
      setRunResult(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
    } finally {
      setRunning(false);
    }
  }

  if (loading || !guardrails) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Configure your trading strategy, risk, and frequency
        </p>
      </div>

      {/* Trading Goal */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Trading Goal</h2>
        <p className="mt-1 text-sm text-zinc-500">
          What should Claude optimize for? This shapes which stocks it considers, how long it holds, and how often it trades.
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TRADING_GOALS.map((goal) => {
            const isActive = guardrails.trading_goal === goal.id;
            return (
              <button
                key={goal.id}
                onClick={() => handleUpdate({ trading_goal: goal.id } as Partial<Guardrails>)}
                disabled={saving}
                className={`rounded-xl border p-4 text-left transition-all ${
                  isActive
                    ? "border-emerald-500 bg-emerald-900/30 ring-1 ring-emerald-500"
                    : "border-zinc-800 bg-zinc-950 hover:border-zinc-700"
                } disabled:opacity-50`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{goal.icon}</span>
                  <span className="text-sm font-semibold text-white">{goal.label}</span>
                </div>
                <p className="mt-2 text-xs text-zinc-400">{goal.description}</p>
                <div className="mt-3 flex items-center gap-3 text-[10px] text-zinc-500">
                  <span className="text-emerald-400">{goal.returns}</span>
                  <span>{goal.frequency}</span>
                </div>
                <p className="mt-1 font-mono text-[10px] text-zinc-600">{goal.tickers}</p>
              </button>
            );
          })}
        </div>
        {saved && <p className="mt-3 text-sm text-emerald-400">Goal applied</p>}
      </div>

      {/* Trading Frequency */}
      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Trading Frequency</h2>
        <p className="mt-1 text-sm text-zinc-500">
          How many times per day should the bot run?
        </p>
        <div className="mt-5 flex gap-3">
          {FREQUENCIES.map((freq) => {
            const isActive = guardrails.trading_frequency === freq.id;
            return (
              <button
                key={freq.id}
                onClick={() => handleUpdate({ trading_frequency: freq.id } as Partial<Guardrails>)}
                disabled={saving}
                className={`flex-1 rounded-xl border p-4 text-center transition-all ${
                  isActive
                    ? "border-blue-500 bg-blue-900/30 ring-1 ring-blue-500"
                    : "border-zinc-800 bg-zinc-950 hover:border-zinc-700"
                } disabled:opacity-50`}
              >
                <p className="text-lg font-bold text-white">{freq.label}</p>
                <p className="mt-1 text-[10px] text-zinc-500">{freq.times}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Risk Profile */}
      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Risk Profile</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Controls position sizing, stop losses, and confidence thresholds
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          {RISK_PROFILES.map((profile) => {
            const isActive = guardrails.risk_profile === profile.id;
            return (
              <button
                key={profile.id}
                onClick={() => handleUpdate({ risk_profile: profile.id } as Partial<Guardrails>)}
                disabled={saving}
                className={`rounded-xl border p-4 text-left transition-all ${
                  isActive
                    ? `${profile.activeBorder} ${profile.activeBg} ring-1 ${profile.ring}`
                    : `${profile.border} ${profile.bg}`
                } disabled:opacity-50`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{profile.icon}</span>
                  <span className="text-sm font-semibold text-white">{profile.label}</span>
                </div>
                <p className="mt-2 text-xs text-zinc-400">{profile.description}</p>
                <p className="mt-2 text-[10px] text-zinc-600">{profile.details}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Fine-Tune Guardrails */}
      <form onSubmit={handleSave} className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Fine-Tune Guardrails</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Override individual settings from the selected profile
        </p>
        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <Field label="Max Total Investment" prefix="$" type="number"
            value={guardrails.max_total_invested}
            onChange={(v) => setGuardrails({ ...guardrails, max_total_invested: Number(v) })}
          />
          <Field label="Max Single Trade Size" prefix="$" type="number"
            value={guardrails.max_single_trade_size}
            onChange={(v) => setGuardrails({ ...guardrails, max_single_trade_size: Number(v) })}
          />
          <Field label="Stop Loss Threshold" suffix="%" type="number" step="0.1"
            value={(guardrails.stop_loss_threshold * 100).toFixed(1)}
            onChange={(v) => setGuardrails({ ...guardrails, stop_loss_threshold: Number(v) / 100 })}
          />
          <Field label="Daily Order Limit" type="number"
            value={guardrails.daily_order_limit}
            onChange={(v) => setGuardrails({ ...guardrails, daily_order_limit: Number(v) })}
          />
          <Field label="Min Confidence to Trade" suffix="%" type="number" step="1"
            value={(guardrails.min_confidence * 100).toFixed(0)}
            onChange={(v) => setGuardrails({ ...guardrails, min_confidence: Number(v) / 100 })}
          />
          <Field label="Max Positions" type="number"
            value={guardrails.max_positions}
            onChange={(v) => setGuardrails({ ...guardrails, max_positions: Number(v) })}
          />
        </div>
        <div className="mt-6 flex items-center gap-4">
          <button type="submit" disabled={saving}
            className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Guardrails"}
          </button>
          {saved && <span className="text-sm text-emerald-400">Saved</span>}
        </div>
      </form>

      {/* Kill Switch */}
      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Emergency Controls</h2>
        <p className="mt-1 text-sm text-zinc-500">Immediately halt all automated trading</p>
        <div className="mt-6">
          <KillSwitchButton
            isActive={guardrails.kill_switch}
            onActivated={() => setGuardrails({ ...guardrails, kill_switch: true })}
          />
        </div>
      </div>

      {/* Manual Run */}
      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Manual Trigger</h2>
        <p className="mt-1 text-sm text-zinc-500">Run one full trading cycle manually</p>
        <div className="mt-6">
          <button
            onClick={() => setShowRunModal(true)}
            disabled={running || guardrails.kill_switch}
            className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {running ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Running Cycle...
              </span>
            ) : (
              "Run Bot Now"
            )}
          </button>
          {guardrails.kill_switch && (
            <p className="mt-2 text-xs text-red-400">Kill switch active — disable first</p>
          )}
          {runResult && (
            <div className="mt-4 rounded-lg bg-zinc-950 px-4 py-3">
              <p className="text-sm text-zinc-300">{runResult}</p>
            </div>
          )}
        </div>
      </div>

      <ConfirmModal open={showRunModal} title="Run Trading Cycle"
        message="This will trigger one full bot cycle: fetch market data, ask Claude for a decision, and potentially execute a trade. Continue?"
        confirmLabel="Run Cycle" confirmClassName="bg-blue-600 hover:bg-blue-700"
        onConfirm={handleRunBot} onCancel={() => setShowRunModal(false)}
      />
    </div>
  );
}

function Field({ label, prefix, suffix, value, onChange, ...inputProps }: {
  label: string; prefix?: string; suffix?: string;
  value: string | number; onChange: (value: string) => void;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label className="block text-sm font-medium text-zinc-300">{label}</label>
      <div className="relative mt-1.5">
        {prefix && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-zinc-500">{prefix}</span>}
        <input {...inputProps} value={value} onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 text-sm text-white placeholder-zinc-500 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 ${
            prefix ? "pl-7 pr-3" : suffix ? "pl-3 pr-7" : "px-3"
          }`}
        />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-zinc-500">{suffix}</span>}
      </div>
    </div>
  );
}
