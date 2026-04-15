"use client";

import { useEffect, useRef, useState } from "react";
import { getGuardrails, triggerRun, updateGuardrails } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Guardrails, TradingGoal } from "@/lib/types";
import { getTimezone, setTimezone } from "@/lib/utils";
import Tip from "@/components/Tip";
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
  const [feedback, setFeedback] = useState<{ type: "saved" | "error"; message: string } | null>(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);
  const [timezone, setTz] = useState("America/New_York");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setTz(getTimezone());
  }, []);

  useEffect(() => {
    if (!user) return;
    getGuardrails()
      .then(setGuardrails)
      .finally(() => setLoading(false));
  }, [user]);

  async function handleUpdate(partial: Partial<Guardrails>) {
    // Debounce: cancel pending save if user clicks another option quickly
    if (saveTimer.current) clearTimeout(saveTimer.current);

    setSaving(true);
    setFeedback(null);

    // Optimistically update UI
    if (guardrails) setGuardrails({ ...guardrails, ...partial });

    saveTimer.current = setTimeout(async () => {
      try {
        const updated = await updateGuardrails(partial);
        setGuardrails(updated);
        setFeedback({ type: "saved", message: "Settings saved" });
        setTimeout(() => setFeedback(null), 2000);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to save settings";
        setFeedback({ type: "error", message });
      } finally {
        setSaving(false);
      }
    }, 300);
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
    } catch (err: unknown) {
      const e = err as Error & { code?: string; ref?: string };
      const code = e?.code || "UNKNOWN";
      const ref = e?.ref || "";
      const message = e?.message || "Unknown error";
      setRunResult(`ERROR [${code}]${ref ? ` ${ref}` : ""}: ${message}`);
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
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-primary">Settings</h1>
          <Tip text="This is where you control the bot's behavior — what it trades, how often, and how much risk it takes. Changes take effect immediately." />
        </div>
        <p className="mt-1 text-sm text-muted">
          Configure your trading strategy, risk, and frequency
        </p>
      </div>

      {feedback && (
        <div className={`mb-4 rounded-lg px-4 py-3 text-sm ${
          feedback.type === "saved"
            ? "border border-emerald-800 bg-emerald-950/30 text-accent"
            : "border border-red-800 bg-red-950/30 text-red-400"
        }`}>
          {feedback.message}
        </div>
      )}

      {/* Trading Goal */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-primary">Trading Goal</h2>
          <Tip text="This is the most important setting. It tells the AI what you're trying to achieve — steady income, maximum growth, or just matching the market. The goal determines which stocks Claude considers and how aggressively it trades." />
        </div>
        <p className="mt-1 text-sm text-muted">
          What should Claude optimize for? This shapes which stocks it considers, how long it holds, and how often it trades.
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TRADING_GOALS.map((goal) => {
            const isActive = guardrails.trading_goal === goal.id;
            return (
              <button
                key={goal.id}
                onClick={() => handleUpdate({ trading_goal: goal.id })}
                disabled={saving}
                className={`rounded-xl border p-4 text-left transition-all ${
                  isActive
                    ? "border-emerald-500 bg-emerald-900/30 ring-1 ring-emerald-500"
                    : "border-border bg-surface hover:border-border-strong"
                } disabled:opacity-50`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{goal.icon}</span>
                  <span className="text-sm font-semibold text-primary">{goal.label}</span>
                </div>
                <p className="mt-2 text-xs text-secondary">{goal.description}</p>
                <div className="mt-3 flex items-center gap-3 text-[10px] text-muted">
                  <span className="text-accent">{goal.returns}</span>
                  <span>{goal.frequency}</span>
                </div>
                <p className="mt-1 font-mono text-[10px] text-muted">{goal.tickers}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Timeline Goal */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-primary">Timeline Goal</h2>
          <Tip text="Set a dollar target and date. The AI will factor this into its urgency — if you're behind schedule, it'll look harder for opportunities. Leave blank to disable." />
        </div>
        <p className="mt-1 text-sm text-muted">
          Where do you want to be, and by when?
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-secondary">Target Amount</label>
            <div className="relative mt-1.5">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">$</span>
              <input
                type="number"
                placeholder="e.g. 500"
                value={guardrails.target_amount ?? ""}
                onChange={(e) => setGuardrails({ ...guardrails, target_amount: e.target.value ? Number(e.target.value) : null })}
                className="w-full rounded-lg border border-border-strong bg-card-alt py-2.5 pl-7 pr-3 text-sm text-primary placeholder-muted transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-secondary">Target Date</label>
            <input
              type="date"
              value={guardrails.target_date ?? ""}
              onChange={(e) => setGuardrails({ ...guardrails, target_date: e.target.value || null })}
              className="mt-1.5 w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2.5 text-sm text-primary transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
        </div>
        {guardrails.target_amount && guardrails.target_date && (
          <p className="mt-3 text-xs text-accent">
            Goal: Grow portfolio to ${guardrails.target_amount.toLocaleString()} by {new Date(guardrails.target_date + "T00:00:00").toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
          </p>
        )}
        <button
          onClick={() => handleUpdate({ target_amount: guardrails.target_amount, target_date: guardrails.target_date })}
          disabled={saving}
          className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-emerald-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Goal"}
        </button>
      </div>

      {/* Trading Frequency */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-primary">Trading Frequency</h2>
          <Tip text="How often the bot analyzes the market and makes decisions. 1x/day is calm and conservative. 5x/day is active — more chances to catch opportunities but also more trading costs." />
        </div>
        <p className="mt-1 text-sm text-muted">
          How many times per day should the bot run?
        </p>
        <div className="mt-5 flex gap-3">
          {FREQUENCIES.map((freq) => {
            const isActive = guardrails.trading_frequency === freq.id;
            return (
              <button
                key={freq.id}
                onClick={() => handleUpdate({ trading_frequency: freq.id })}
                disabled={saving}
                className={`flex-1 rounded-xl border p-4 text-center transition-all ${
                  isActive
                    ? "border-blue-500 bg-blue-900/30 ring-1 ring-blue-500"
                    : "border-border bg-surface hover:border-border-strong"
                } disabled:opacity-50`}
              >
                <p className="text-lg font-bold text-primary">{freq.label}</p>
                <p className="mt-1 text-[10px] text-muted">{freq.times}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Risk Profile */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-primary">Risk Profile</h2>
          <Tip text="How much risk you're comfortable with. Conservative = small positions, strict limits, rarely trades. Aggressive = larger positions, looser limits, trades more often. This overrides the fine-tune settings below with preset values." />
        </div>
        <p className="mt-1 text-sm text-muted">
          Controls position sizing, stop losses, and confidence thresholds
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          {RISK_PROFILES.map((profile) => {
            const isActive = guardrails.risk_profile === profile.id;
            return (
              <button
                key={profile.id}
                onClick={() => handleUpdate({ risk_profile: profile.id })}
                disabled={saving}
                className={`rounded-xl border p-4 text-left transition-all ${
                  isActive
                    ? `${profile.activeBorder} ${profile.activeBg} ring-1 ${profile.ring}`
                    : `${profile.border} ${profile.bg}`
                } disabled:opacity-50`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{profile.icon}</span>
                  <span className="text-sm font-semibold text-primary">{profile.label}</span>
                </div>
                <p className="mt-2 text-xs text-secondary">{profile.description}</p>
                <p className="mt-2 text-[10px] text-muted">{profile.details}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Fine-Tune Guardrails */}
      <form onSubmit={handleSave} className="mt-6 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-primary">Fine-Tune Guardrails</h2>
          <Tip text="Guardrails are safety limits that prevent the bot from doing anything too risky. Even if Claude wants to make a big trade, guardrails can block it. Think of them as guard rails on a highway — they keep you from going off the edge." />
        </div>
        <p className="mt-1 text-sm text-muted">
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
            className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-primary transition-colors hover:bg-emerald-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Guardrails"}
          </button>
          {feedback?.type === "saved" && <span className="text-sm text-accent">{feedback.message}</span>}
          {feedback?.type === "error" && <span className="text-sm text-red-400">{feedback.message}</span>}
        </div>
      </form>

      {/* Kill Switch */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-primary">Emergency Controls</h2>
          <Tip text="The kill switch immediately stops ALL automated trading. The bot won't buy or sell anything until you turn it back off. Use this if something seems wrong or you want to pause trading." />
        </div>
        <p className="mt-1 text-sm text-muted">Immediately halt all automated trading</p>
        <div className="mt-6">
          <KillSwitchButton
            isActive={guardrails.kill_switch}
            onToggled={() => setGuardrails({ ...guardrails, kill_switch: !guardrails.kill_switch })}
          />
        </div>
      </div>

      {/* Manual Run */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-primary">Manual Trigger</h2>
          <span className="rounded bg-amber-900/30 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-400">
            Testing Only
          </span>
        </div>
        <p className="mt-1 text-sm text-muted">
          Run one full trading cycle manually. The bot runs automatically on your configured schedule — this is for testing only.
        </p>
        <div className="mt-6">
          <button
            onClick={() => setShowRunModal(true)}
            disabled={running || guardrails.kill_switch}
            className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-primary transition-colors hover:bg-blue-700 disabled:opacity-50"
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
            <div className={`mt-4 rounded-lg px-4 py-3 ${
              runResult.startsWith("ERROR")
                ? "border border-red-800 bg-red-950/30"
                : "bg-surface"
            }`}>
              {runResult.startsWith("ERROR") ? (
                <>
                  <p className="text-sm font-medium text-red-400">
                    {runResult.split("]: ")[0]}]
                  </p>
                  <p className="mt-1 text-sm text-secondary">
                    {runResult.split("]: ")[1]}
                  </p>
                </>
              ) : (
                <p className="text-sm text-secondary">{runResult}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Alpaca Account */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Broker Account</h2>
        <p className="mt-1 text-sm text-muted">
          Manage your Alpaca account, deposit/withdraw funds, and view order history
        </p>
        <div className="mt-4">
          <a
            href="https://app.alpaca.markets"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-border-strong bg-card-alt px-4 py-2.5 text-sm font-medium text-secondary transition-colors hover:bg-border-strong"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-4.5-4.5h6m0 0v6m0-6L10.5 13.5" />
            </svg>
            Open Alpaca Dashboard
          </a>
          <p className="mt-2 text-xs text-muted">
            Deposits, withdrawals, and order history are managed directly on Alpaca
          </p>
        </div>
      </div>

      {/* Display Timezone */}
      <div className="mt-6 rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-primary">Display Timezone</h2>
        <p className="mt-1 text-sm text-muted">
          All dates and times across the app will display in this timezone
        </p>
        <div className="mt-4 max-w-xs">
          <select
            value={timezone}
            onChange={(e) => {
              setTz(e.target.value);
              setTimezone(e.target.value);
            }}
            className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2.5 text-sm text-primary focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            <option value="America/New_York">Eastern (ET)</option>
            <option value="America/Chicago">Central (CT)</option>
            <option value="America/Denver">Mountain (MT)</option>
            <option value="America/Los_Angeles">Pacific (PT)</option>
            <option value="America/Anchorage">Alaska (AKT)</option>
            <option value="Pacific/Honolulu">Hawaii (HT)</option>
            <option value="UTC">UTC</option>
          </select>
          <p className="mt-2 text-xs text-muted">
            Current: {new Date().toLocaleTimeString("en-US", { timeZone: timezone, hour: "numeric", minute: "2-digit", timeZoneName: "short" })}
          </p>
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
      <label className="block text-sm font-medium text-secondary">{label}</label>
      <div className="relative mt-1.5">
        {prefix && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">{prefix}</span>}
        <input {...inputProps} value={value} onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-lg border border-border-strong bg-card-alt py-2.5 text-sm text-primary placeholder-zinc-500 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 ${
            prefix ? "pl-7 pr-3" : suffix ? "pl-3 pr-7" : "px-3"
          }`}
        />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted">{suffix}</span>}
      </div>
    </div>
  );
}
