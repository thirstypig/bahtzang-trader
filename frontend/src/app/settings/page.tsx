"use client";

import { useEffect, useState } from "react";
import { getGuardrails, triggerRun, updateGuardrails } from "@/lib/api";
import { Guardrails } from "@/lib/types";
import KillSwitchButton from "@/components/KillSwitchButton";
import ConfirmModal from "@/components/ConfirmModal";

export default function SettingsPage() {
  const [guardrails, setGuardrails] = useState<Guardrails | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);

  useEffect(() => {
    getGuardrails()
      .then(setGuardrails)
      .finally(() => setLoading(false));
  }, []);

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
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Configure trading guardrails and bot controls
        </p>
      </div>

      {/* Guardrails Form */}
      <form onSubmit={handleSave} className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-white">Guardrails</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Safety limits that override Claude&apos;s decisions
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
