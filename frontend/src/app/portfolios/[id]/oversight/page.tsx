"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getOversightActivity } from "@/lib/api";
import type { OversightActivity } from "@/lib/types";

function ActionBadge({ action, diverged }: { action: string; diverged?: boolean }) {
  const base = "inline-block px-2 py-0.5 rounded text-xs font-semibold uppercase";
  if (action === "buy") return <span className={`${base} bg-pos/15 text-pos`}>buy</span>;
  if (action === "sell") return <span className={`${base} bg-neg/15 text-neg`}>sell</span>;
  return <span className={`${base} ${diverged ? "bg-orange-500/15 text-orange-500" : "bg-muted/20 text-muted"}`}>{action}</span>;
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bz-glass rounded-xl p-4">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );
}

export default function OversightActivityPage() {
  const params = useParams();
  const portfolioId = Number(params.id);

  const [data, setData] = useState<OversightActivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const result = await getOversightActivity(portfolioId);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load oversight activity");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [portfolioId]);

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-muted">Loading oversight activity...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <Link href={`/portfolios/${portfolioId}`} className="text-accent hover:underline text-sm mb-4 inline-block">
          ← Back to Portfolio
        </Link>
        <div className="p-4 bg-neg/10 text-neg border border-neg/30 rounded-xl">{error}</div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      <div className="mb-8">
        <Link href={`/portfolios/${portfolioId}`} className="text-accent hover:underline text-sm mb-4 inline-block">
          ← Back to Portfolio
        </Link>
        <h1 className="text-2xl font-bold">Oversight Activity</h1>
        <p className="text-muted mt-1 text-sm">
          Every decision where the strategy recommended an action and Claude reviewed it.
        </p>
      </div>

      {!data || data.summary.total === 0 ? (
        <div className="bz-glass rounded-xl p-8 text-center text-muted">
          <p className="text-lg mb-2">No oversight decisions yet</p>
          <p className="text-sm">
            Oversight activity appears here when this portfolio runs in{" "}
            <span className="font-medium text-primary">Rules + Claude oversight</span> mode.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4 mb-8">
            <StatCard label="Total Decisions" value={data.summary.total} />
            <StatCard
              label="Confirmed by Claude"
              value={data.summary.confirmed}
              sub={`${data.summary.confirmed_pct}% of decisions`}
            />
            <StatCard
              label="Overridden by Claude"
              value={data.summary.overridden}
              sub={`${data.summary.overridden_pct}% of decisions`}
            />
          </div>

          <div className="space-y-3">
            {data.records.map((rec) => (
              <div key={rec.id} className={`bz-glass rounded-xl p-5 ${rec.diverged ? "border border-orange-500/30" : ""}`}>
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-semibold">{rec.ticker}</span>
                    <span className="text-xs text-muted">
                      {new Date(rec.timestamp).toLocaleString()}
                    </span>
                    {rec.diverged && (
                      <span className="text-xs bg-orange-500/15 text-orange-500 px-2 py-0.5 rounded font-medium">
                        Overridden
                      </span>
                    )}
                    {!rec.diverged && (
                      <span className="text-xs bg-pos/10 text-pos px-2 py-0.5 rounded font-medium">
                        Confirmed
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted shrink-0">
                    {rec.executed ? "Executed" : "Blocked"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-muted mb-1 uppercase tracking-wide font-medium">Strategy Signal</p>
                    <div className="flex items-center gap-2 mb-1">
                      <ActionBadge action={rec.rules_recommendation.action} />
                      {rec.rules_recommendation.quantity != null && (
                        <span className="text-muted text-xs">×{rec.rules_recommendation.quantity}</span>
                      )}
                      {rec.rules_recommendation.confidence != null && (
                        <span className="text-muted text-xs">
                          {(rec.rules_recommendation.confidence * 100).toFixed(0)}% conf
                        </span>
                      )}
                    </div>
                    {rec.rules_recommendation.reasoning && (
                      <p className="text-xs text-muted leading-snug line-clamp-2">
                        {rec.rules_recommendation.reasoning}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs text-muted mb-1 uppercase tracking-wide font-medium">Final Decision</p>
                    <div className="flex items-center gap-2 mb-1">
                      <ActionBadge action={rec.final_action} diverged={rec.diverged} />
                      {rec.diverged && (
                        <span className="text-xs text-orange-500">← changed</span>
                      )}
                    </div>
                    {rec.claude_reasoning && (
                      <p className="text-xs text-muted leading-snug line-clamp-2">
                        {rec.claude_reasoning}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
