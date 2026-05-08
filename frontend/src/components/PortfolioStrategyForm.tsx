"use client";

import { useState } from "react";
import { updatePortfolioStrategy } from "@/lib/api";
import type { PortfolioStrategy } from "@/lib/api";

interface PortfolioStrategyFormProps {
  portfolioId: number;
  strategy: PortfolioStrategy;
  onSave: () => void;
}

export default function PortfolioStrategyForm({
  portfolioId,
  strategy,
  onSave,
}: PortfolioStrategyFormProps) {
  const [cooldownHours, setCooldownHours] = useState(
    strategy.cooldown_hours.toString()
  );
  const [minConfidence, setMinConfidence] = useState(
    strategy.min_confidence.toString()
  );
  const [respectWashSale, setRespectWashSale] = useState(
    strategy.respect_wash_sale
  );
  const [kellyFraction, setKellyFraction] = useState(
    strategy.kelly_fraction.toString()
  );
  const [circuitBreakerDaily, setCircuitBreakerDaily] = useState(
    strategy.circuit_breaker_daily_pct.toString()
  );
  const [circuitBreakerWeekly, setCircuitBreakerWeekly] = useState(
    strategy.circuit_breaker_weekly_pct.toString()
  );
  const [reason, setReason] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      if (!reason.trim()) {
        setError("Reason for change is required");
        return;
      }

      const updates: Partial<PortfolioStrategy> & { reason: string } = {
        reason: reason.trim(),
      };

      const cooldownNum = parseFloat(cooldownHours);
      if (!isNaN(cooldownNum)) updates.cooldown_hours = cooldownNum;

      const confidenceNum = parseFloat(minConfidence);
      if (!isNaN(confidenceNum)) updates.min_confidence = confidenceNum;

      updates.respect_wash_sale = respectWashSale;

      const kellyNum = parseFloat(kellyFraction);
      if (!isNaN(kellyNum)) updates.kelly_fraction = kellyNum;

      const dailyNum = parseFloat(circuitBreakerDaily);
      if (!isNaN(dailyNum)) updates.circuit_breaker_daily_pct = dailyNum;

      const weeklyNum = parseFloat(circuitBreakerWeekly);
      if (!isNaN(weeklyNum)) updates.circuit_breaker_weekly_pct = weeklyNum;

      await updatePortfolioStrategy(portfolioId, updates);
      setSuccess(true);
      setReason("");
      setTimeout(() => setSuccess(false), 3000);
      onSave();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update strategy");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-4 bg-red-100 text-red-800 rounded-lg">{error}</div>
        )}

        {success && (
          <div className="p-4 bg-green-100 text-green-800 rounded-lg">
            Strategy updated successfully
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Cooldown Hours
            </label>
            <input
              type="number"
              value={cooldownHours}
              onChange={(e) => setCooldownHours(e.target.value)}
              step="0.1"
              className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <p className="text-xs text-muted mt-1">
              Hours between trades on same ticker
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Min Confidence
            </label>
            <input
              type="number"
              value={minConfidence}
              onChange={(e) => setMinConfidence(e.target.value)}
              step="0.01"
              min="0"
              max="1"
              className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <p className="text-xs text-muted mt-1">Minimum (0.0 - 1.0)</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Kelly Fraction
            </label>
            <input
              type="number"
              value={kellyFraction}
              onChange={(e) => setKellyFraction(e.target.value)}
              step="0.01"
              min="0"
              max="1"
              className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <p className="text-xs text-muted mt-1">
              Position sizing fraction (0.0 - 1.0)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Circuit Breaker Daily %
            </label>
            <input
              type="number"
              value={circuitBreakerDaily}
              onChange={(e) => setCircuitBreakerDaily(e.target.value)}
              step="0.1"
              className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <p className="text-xs text-muted mt-1">Daily P&L loss threshold %</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Circuit Breaker Weekly %
            </label>
            <input
              type="number"
              value={circuitBreakerWeekly}
              onChange={(e) => setCircuitBreakerWeekly(e.target.value)}
              step="0.1"
              className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <p className="text-xs text-muted mt-1">Weekly P&L loss threshold %</p>
          </div>

          <div className="flex items-center pt-2">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={respectWashSale}
                onChange={(e) => setRespectWashSale(e.target.checked)}
                className="w-4 h-4 rounded border border-border"
              />
              <span className="ml-3 text-sm font-medium">Respect Wash Sale</span>
            </label>
            <p className="text-xs text-muted ml-auto">
              30-day rule enforcement
            </p>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            Reason for Change
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain why you're making this change (required for audit log)"
            className="w-full px-4 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
            rows={3}
          />
        </div>

        <button
          type="submit"
          disabled={saving}
          className="px-4 py-3 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 font-medium"
        >
          {saving ? "Saving..." : "Save Strategy"}
        </button>
      </form>

      {strategy.audit_log.length > 0 && (
        <div className="mt-8 border-t border-border pt-6">
          <h3 className="text-lg font-semibold mb-4">Audit Log</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 text-muted font-medium">
                    Date
                  </th>
                  <th className="text-left py-2 px-3 text-muted font-medium">
                    User
                  </th>
                  <th className="text-left py-2 px-3 text-muted font-medium">
                    Action
                  </th>
                  <th className="text-left py-2 px-3 text-muted font-medium">
                    Change
                  </th>
                  <th className="text-left py-2 px-3 text-muted font-medium">
                    Reason
                  </th>
                </tr>
              </thead>
              <tbody>
                {strategy.audit_log.map((entry) => (
                  <tr
                    key={entry.id}
                    className="border-b border-border hover:bg-card-alt"
                  >
                    <td className="py-2 px-3 text-xs">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2 px-3 text-xs">{entry.user_email}</td>
                    <td className="py-2 px-3 text-xs font-medium">
                      {entry.action}
                    </td>
                    <td className="py-2 px-3 text-xs">
                      {entry.old_value && entry.new_value ? (
                        <span>
                          {entry.old_value} → {entry.new_value}
                        </span>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-xs text-muted">
                      {entry.reason || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
