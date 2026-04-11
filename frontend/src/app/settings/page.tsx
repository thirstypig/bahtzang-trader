"use client";

import { useEffect, useState } from "react";
import { getGuardrails, triggerRun, updateGuardrails } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Guardrails } from "@/lib/types";
import KillSwitchButton from "@/components/KillSwitchButton";
import Spinner from "@/components/Spinner";
import ConfirmModal from "@/components/ConfirmModal";

const RISK_PROFILES = [
  {
    id: "conservative" as const,
    label: "Conservative",
    icon: "🛡️",
    color: "emerald",
    description: "Preserve capital. Few trades, high conviction only.",
    details: "30% max invested · 5% per trade · 3% stop loss · 75% min confidence · 3 trades/day · 5 positions max",
    border: "border-emerald-800",
    bg: "bg-emerald-900/20",
    activeBorder: "border-emerald-500",
    activeBg: "bg-emerald-900/40",
    ring: "ring-emerald-500",
  },
  {
    id: "moderate" as const,
    label: "Moderate",
    icon: "⚖️",
    color: "blue",
    description: "Balanced risk and reward. Steady growth.",
    details: "60% max invested · 10% per trade · 5% stop loss · 60% min confidence · 5 trades/day · 10 positions max",
    border: "border-blue-800",
    bg: "bg-blue-900/20",
    activeBorder: "border-blue-500",
    activeBg: "bg-blue-900/40",
    ring: "ring-blue-500",
  },
  {
    id: "aggressive" as const,
    label: "Aggressive",
    icon: "🔥",
    color: "amber",
    description: "Maximize returns. More trades, higher risk.",
    details: "90% max invested · 20% per trade · 8% stop loss · 45% min confidence · 10 trades/day · 20 positions max",
    border: "border-amber-800",
    bg: "bg-amber-900/20",
    activeBorder: "border-amber-500",
    activeBg: "bg-amber-900/40",
    ring: "ring-amber-500",
  },
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

  async function handleProfileSelect(profile: "conservative" | "moderate" | "aggressive") {
    if (!guardrails) return;
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateGuardrails({ risk_profile: profile } as Partial<Guardrails>);
      setGuardrails(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error("Failed to apply profile:", err);
    } finally {
      setSaving(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!guardrails) return;
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateGuardrails(guardrails);
      setGuardrails(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSaving(false);
    }
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
          Configure risk profile and trading guardrails
        </p>
      </div>

      {/* Risk Profile Selector */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Risk Profile</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Select a preset — all guardrails auto-adjust. You can still fine-tune individual settings below.
        </p>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          {RISK_PROFILES.map((profile) => {
            const isActive = guardrails.risk_profile === profile.id;
            return (
              <button
                key={profile.id}
                onClick={() => handleProfileSelect(profile.id)}
                disabled={saving}
                className={`rounded-xl border p-4 text-left transition-all ${
                  isActive
                    ? `${profile.activeBorder} ${profile.activeBg} ring-1 ${profile.ring}`
                    : `${profile.border} ${profile.bg} hover:${profile.activeBg}`
                } disabled:opacity-50`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{profile.icon}</span>
                  <span className="text-sm font-semibold text-white">{profile.label}</span>
                  {isActive && (
                    <span className="ml-auto text-[10px] font-medium text-emerald-400">ACTIVE</span>
                  )}
                </div>
                <p className="mt-2 text-xs text-zinc-400">{profile.description}</p>
                <p className="mt-2 text-[10px] text-zinc-600 leading-relaxed">{profile.details}</p>
              </button>
            );
          })}
        </div>
        {saved && (
          <p className="mt-3 text-sm text-emerald-400">Profile applied successfully</p>
        )}
      </div>

      {/* Fine-Tune Guardrails */}
      <form onSubmit={handleSave} className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Fine-Tune Guardrails</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Override individual settings from the selected profile
        </p>

        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <Field
            label="Max Total Investment"
            prefix="$"
            type="number"
            value={guardrails.max_total_invested}
            onChange={(v) =>
              setGuardrails({ ...guardrails, max_total_invested: Number(v) })
            }
          />
          <Field
            label="Max Single Trade Size"
            prefix="$"
            type="number"
            value={guardrails.max_single_trade_size}
            onChange={(v) =>
              setGuardrails({ ...guardrails, max_single_trade_size: Number(v) })
            }
          />
          <Field
            label="Stop Loss Threshold"
            suffix="%"
            type="number"
            step="0.1"
            value={(guardrails.stop_loss_threshold * 100).toFixed(1)}
            onChange={(v) =>
              setGuardrails({
                ...guardrails,
                stop_loss_threshold: Number(v) / 100,
              })
            }
          />
          <Field
            label="Daily Order Limit"
            type="number"
            value={guardrails.daily_order_limit}
            onChange={(v) =>
              setGuardrails({ ...guardrails, daily_order_limit: Number(v) })
            }
          />
          <Field
            label="Min Confidence to Trade"
            suffix="%"
            type="number"
            step="1"
            value={(guardrails.min_confidence * 100).toFixed(0)}
            onChange={(v) =>
              setGuardrails({
                ...guardrails,
                min_confidence: Number(v) / 100,
              })
            }
          />
          <Field
            label="Max Positions"
            type="number"
            value={guardrails.max_positions}
            onChange={(v) =>
              setGuardrails({ ...guardrails, max_positions: Number(v) })
            }
          />
        </div>

        <div className="mt-6 flex items-center gap-4">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Guardrails"}
          </button>
          {saved && (
            <span className="text-sm text-emerald-400">Saved successfully</span>
          )}
        </div>
      </form>

      {/* Kill Switch */}
      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Emergency Controls</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Immediately halt all automated trading activity
        </p>
        <div className="mt-6 flex items-center gap-6">
          <KillSwitchButton
            isActive={guardrails.kill_switch}
            onActivated={() =>
              setGuardrails({ ...guardrails, kill_switch: true })
            }
          />
        </div>
      </div>

      {/* Manual Run */}
      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Manual Trigger</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Run one full trading cycle manually
        </p>
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
            <p className="mt-2 text-xs text-red-400">
              Kill switch is active — disable it before running
            </p>
          )}
          {runResult && (
            <div className="mt-4 rounded-lg bg-zinc-950 px-4 py-3">
              <p className="text-sm text-zinc-300">{runResult}</p>
            </div>
          )}
        </div>
      </div>

      <ConfirmModal
        open={showRunModal}
        title="Run Trading Cycle"
        message="This will trigger one full bot cycle: fetch market data, ask Claude for a decision, and potentially execute a trade. Continue?"
        confirmLabel="Run Cycle"
        confirmClassName="bg-blue-600 hover:bg-blue-700"
        onConfirm={handleRunBot}
        onCancel={() => setShowRunModal(false)}
      />
    </div>
  );
}

function Field({
  label,
  prefix,
  suffix,
  value,
  onChange,
  ...inputProps
}: {
  label: string;
  prefix?: string;
  suffix?: string;
  value: string | number;
  onChange: (value: string) => void;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label className="block text-sm font-medium text-zinc-300">{label}</label>
      <div className="relative mt-1.5">
        {prefix && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-zinc-500">
            {prefix}
          </span>
        )}
        <input
          {...inputProps}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 text-sm text-white placeholder-zinc-500 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 ${
            prefix ? "pl-7 pr-3" : suffix ? "pl-3 pr-7" : "px-3"
          }`}
        />
        {suffix && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-zinc-500">
            {suffix}
          </span>
        )}
      </div>
    </div>
  );
}
