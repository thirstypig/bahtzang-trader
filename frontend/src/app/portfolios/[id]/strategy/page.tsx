"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getPortfolioDetail,
  getStrategies,
  updatePortfolio,
} from "@/lib/api";
import type { DecisionMode, InvestmentPlan, StrategyInfo } from "@/lib/types";
import ConfirmModal from "@/components/ConfirmModal";
import DecisionModeBadge from "@/components/DecisionModeBadge";

// ---------------------------------------------------------------------------
// Decision mode metadata
// ---------------------------------------------------------------------------

const DECISION_MODES: {
  value: DecisionMode;
  label: string;
  icon: string;
  description: string;
}[] = [
  {
    value: "claude_decides",
    label: "Claude decides",
    icon: "🤖",
    description:
      "Claude Sonnet weighs all signals and makes each trade decision. Higher API cost, non-reproducible, adapts to context.",
  },
  {
    value: "rules_decide",
    label: "Rules decide",
    icon: "⚙️",
    description:
      "A deterministic strategy makes every decision. Cheap, reproducible, fully backtestable. Claude is not called.",
  },
  {
    value: "rules_with_claude_oversight",
    label: "Rules + Claude oversight",
    icon: "🔬",
    description:
      "Strategy produces a recommendation; Claude reviews and can override only in exceptional circumstances (e.g., earnings event). Best of both, higher cost.",
  },
];

function ModeCard({
  mode,
  selected,
  onSelect,
}: {
  mode: (typeof DECISION_MODES)[number];
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "text-left p-4 rounded-xl border transition-all duration-150 w-full",
        selected
          ? "border-accent bg-accent/10 ring-1 ring-accent"
          : "border-border bz-glass-soft hover:border-accent/50",
      ].join(" ")}
    >
      <div className="text-2xl mb-2">{mode.icon}</div>
      <div className="font-semibold text-sm">{mode.label}</div>
      <div className="text-xs text-muted leading-snug mt-1">{mode.description}</div>
    </button>
  );
}

function renderParamInput(
  param: StrategyInfo["params"][number],
  value: string,
  onChange: (key: string, val: string) => void,
) {
  const id = `param-${param.key}`;
  if (param.type === "boolean") {
    return (
      <div key={param.key} className="flex items-center gap-3 col-span-2">
        <input
          id={id}
          type="checkbox"
          checked={value === "true"}
          onChange={(e) => onChange(param.key, e.target.checked ? "true" : "false")}
          className="w-4 h-4 rounded border border-border"
        />
        <label htmlFor={id} className="text-sm font-medium">
          {param.label}
        </label>
      </div>
    );
  }
  return (
    <div key={param.key}>
      <label htmlFor={id} className="block text-sm font-medium mb-1">
        {param.label}
      </label>
      <input
        id={id}
        type={param.type === "number" || param.type === "int" ? "number" : "text"}
        value={value}
        onChange={(e) => onChange(param.key, e.target.value)}
        placeholder={
          param.type === "list" ? "AAPL, MSFT, NVDA" : String(param.default ?? "")
        }
        className="w-full px-3 py-2 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent text-sm"
      />
      {param.type === "list" && (
        <p className="text-xs text-muted mt-1">Comma-separated tickers</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DecisionEnginePage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = Number(params.id);

  // Portfolio state
  const [portfolio, setPortfolio] = useState<InvestmentPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Strategies
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const strategiesLoaded = useRef(false);

  // Form state — mirrors portfolio values once loaded
  const [decisionMode, setDecisionMode] = useState<DecisionMode>("claude_decides");
  const [strategyId, setStrategyId] = useState("");
  const [strategyParams, setStrategyParams] = useState<Record<string, string>>({});

  // The decision_mode the portfolio currently has (for change detection)
  const originalMode = useRef<DecisionMode>("claude_decides");

  // Confirmation modal
  const [pendingMode, setPendingMode] = useState<DecisionMode | null>(null);

  // Save state
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const selectedStrategy = strategies.find((s) => s.id === strategyId) ?? null;

  // Load portfolio
  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setLoadError(null);
        const data = await getPortfolioDetail(portfolioId);
        setPortfolio(data);

        const mode = data.decision_mode ?? "claude_decides";
        setDecisionMode(mode);
        originalMode.current = mode;
        setStrategyId(data.strategy_id ?? "");

        // Pre-fill string representations of existing params
        const paramStrings: Record<string, string> = {};
        for (const [k, v] of Object.entries(data.strategy_params ?? {})) {
          paramStrings[k] = Array.isArray(v) ? (v as string[]).join(", ") : String(v);
        }
        setStrategyParams(paramStrings);

        // Load strategies if portfolio is already in a rules mode
        if (mode !== "claude_decides") loadStrategies();
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : "Failed to load portfolio");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [portfolioId]);

  async function loadStrategies() {
    if (strategiesLoaded.current) return;
    try {
      setStrategiesLoading(true);
      const data = await getStrategies();
      setStrategies(data);
      strategiesLoaded.current = true;
    } catch {
      // non-fatal
    } finally {
      setStrategiesLoading(false);
    }
  }

  function handleModeClick(mode: DecisionMode) {
    if (mode === decisionMode) return;
    // Show confirmation modal when changing away from the saved mode
    if (mode !== originalMode.current) {
      setPendingMode(mode);
    } else {
      applyMode(mode);
    }
  }

  function applyMode(mode: DecisionMode) {
    setDecisionMode(mode);
    if (mode !== "claude_decides") loadStrategies();
    if (mode === "claude_decides") {
      setStrategyId("");
      setStrategyParams({});
    }
    setPendingMode(null);
  }

  function handleStrategyChange(id: string) {
    setStrategyId(id);
    const strat = strategies.find((s) => s.id === id);
    if (strat) {
      const defaults: Record<string, string> = {};
      for (const p of strat.params) {
        defaults[p.key] = String(p.default ?? "");
      }
      setStrategyParams(defaults);
    } else {
      setStrategyParams({});
    }
  }

  function handleParamChange(key: string, val: string) {
    setStrategyParams((prev) => ({ ...prev, [key]: val }));
  }

  function buildStrategyParams(): Record<string, unknown> {
    if (!selectedStrategy) return {};
    const result: Record<string, unknown> = {};
    for (const p of selectedStrategy.params) {
      const val = strategyParams[p.key] ?? "";
      if (p.type === "number" || p.type === "int") {
        result[p.key] = parseFloat(val) || (p.default ?? 0);
      } else if (p.type === "boolean") {
        result[p.key] = val === "true";
      } else if (p.type === "list") {
        result[p.key] = val.split(",").map((s) => s.trim()).filter(Boolean);
      } else {
        result[p.key] = val;
      }
    }
    return result;
  }

  async function handleSave() {
    if (!portfolio) return;
    if (decisionMode !== "claude_decides" && !strategyId) {
      setSaveError("A strategy is required when using Rules or Hybrid mode");
      return;
    }
    try {
      setSaving(true);
      setSaveError(null);
      setSaveSuccess(false);
      await updatePortfolio(portfolioId, {
        decision_mode: decisionMode,
        strategy_id: strategyId || null,
        strategy_params: buildStrategyParams(),
      });
      originalMode.current = decisionMode;
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-muted">Loading...</div>
      </div>
    );
  }

  if (loadError || !portfolio) {
    return (
      <div className="p-8">
        <Link
          href={`/portfolios/${portfolioId}`}
          className="text-accent hover:underline text-sm mb-4 inline-block"
        >
          ← Back to Portfolio
        </Link>
        <div className="p-4 bg-neg/10 text-neg border border-neg/30 rounded-xl">
          {loadError || "Portfolio not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-3xl">
      <div className="mb-8">
        <Link
          href={`/portfolios/${portfolioId}`}
          className="text-accent hover:underline text-sm mb-4 inline-block"
        >
          ← Back to {portfolio.name}
        </Link>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-bold">Decision Engine</h1>
          <DecisionModeBadge
            mode={decisionMode}
            strategyName={strategyId || portfolio.strategy_id}
          />
        </div>
        <p className="text-muted mt-1 text-sm">
          Controls which system makes trade decisions for this portfolio. Changes affect future trades only.
        </p>
      </div>

      {saveError && (
        <div className="mb-6 p-4 bg-neg/10 text-neg border border-neg/30 rounded-xl">
          {saveError}
        </div>
      )}
      {saveSuccess && (
        <div className="mb-6 p-4 bg-pos/10 text-pos border border-pos/30 rounded-xl">
          Decision engine saved.
        </div>
      )}

      <div className="space-y-6">
        {/* Mode selector */}
        <div>
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">
            Decision Mode
          </h2>
          <div className="grid grid-cols-3 gap-3">
            {DECISION_MODES.map((dm) => (
              <ModeCard
                key={dm.value}
                mode={dm}
                selected={decisionMode === dm.value}
                onSelect={() => handleModeClick(dm.value)}
              />
            ))}
          </div>
        </div>

        {/* Strategy picker */}
        {decisionMode !== "claude_decides" && (
          <div className="bz-glass rounded-xl p-6 space-y-4">
            <h2 className="text-sm font-semibold text-muted uppercase tracking-wide">
              Strategy
            </h2>
            {strategiesLoading ? (
              <p className="text-sm text-muted">Loading strategies...</p>
            ) : (
              <select
                value={strategyId}
                onChange={(e) => handleStrategyChange(e.target.value)}
                className="w-full px-4 py-2.5 border border-border rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <option value="">— Select a strategy —</option>
                {strategies.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — {s.description}
                  </option>
                ))}
              </select>
            )}

            {selectedStrategy && selectedStrategy.params.length > 0 && (
              <div>
                <h3 className="text-sm font-medium mb-3">Strategy Parameters</h3>
                <div className="grid grid-cols-2 gap-3">
                  {selectedStrategy.params.map((p) =>
                    renderParamInput(
                      p,
                      strategyParams[p.key] ?? String(p.default ?? ""),
                      handleParamChange,
                    )
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Save */}
        <div className="flex gap-4">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-3 bg-accent text-white rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 font-medium"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <button
            type="button"
            onClick={() => router.push(`/portfolios/${portfolioId}`)}
            className="px-6 py-3 border border-border rounded-xl hover:bg-card transition-colors font-medium"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* Confirmation modal for mode changes */}
      <ConfirmModal
        open={pendingMode !== null}
        title="Change decision mode?"
        message="Changing decision mode will affect future trades only. Existing positions are not closed. Past trades are unchanged. Continue?"
        confirmLabel="Yes, change mode"
        confirmClassName="bg-accent hover:opacity-90"
        onConfirm={() => pendingMode && applyMode(pendingMode)}
        onCancel={() => setPendingMode(null)}
      />
    </div>
  );
}
