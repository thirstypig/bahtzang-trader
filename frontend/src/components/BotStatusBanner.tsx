"use client";

import { useEffect, useState } from "react";
import { getBotStatus, BotStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { GOAL_CONFIG } from "@/lib/constants";
import { getTimezone } from "@/lib/utils";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatNextRun(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();

  if (diffMs < 0) return "any moment";

  const hours = Math.floor(diffMs / 3600000);
  const mins = Math.floor((diffMs % 3600000) / 60000);

  if (hours > 24) {
    return d.toLocaleDateString("en-US", { timeZone: getTimezone(), weekday: "short" }) +
      " " + d.toLocaleTimeString("en-US", { timeZone: getTimezone(), hour: "numeric", minute: "2-digit" });
  }
  if (hours > 0) return `in ${hours}h ${mins}m`;
  return `in ${mins}m`;
}

export default function BotStatusBanner() {
  const { user } = useAuth();
  const [status, setStatus] = useState<BotStatus | null>(null);

  useEffect(() => {
    if (!user) return;
    getBotStatus().then(setStatus).catch(() => {});

    // Refresh every 60 seconds
    const interval = setInterval(() => {
      getBotStatus().then(setStatus).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [user]);

  if (!status) return null;

  const isHalted = status.kill_switch;

  return (
    <div
      className={`mb-6 rounded-xl border p-4 ${
        isHalted
          ? "border-red-800 bg-red-950/20"
          : "border-emerald-800/50 bg-emerald-950/10"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              isHalted ? "bg-red-500" : "bg-emerald-500 animate-pulse"
            }`}
          />
          <span
            className={`text-sm font-semibold ${
              isHalted ? "text-red-400" : "text-accent"
            }`}
          >
            {isHalted ? "Bot Halted" : "Bot Active"}
          </span>
        </div>

        {/* Frequency */}
        <div className="text-xs text-secondary">
          <span className="text-muted">Schedule:</span>{" "}
          {status.frequency}/day ({status.schedule_times.join(", ")})
        </div>

        {/* Strategy */}
        <div className="text-xs text-secondary">
          <span className="text-muted">Goal:</span>{" "}
          {GOAL_CONFIG[status.trading_goal as keyof typeof GOAL_CONFIG]?.label || status.trading_goal}
          <span className="mx-1 text-zinc-700">·</span>
          <span className="text-muted">Risk:</span>{" "}
          <span className="capitalize">{status.risk_profile}</span>
        </div>

        {/* Last run */}
        {status.last_run && (
          <div className="text-xs text-secondary">
            <span className="text-muted">Last:</span>{" "}
            {status.last_action?.toUpperCase()} {status.last_ticker}{" "}
            <span className="text-muted">({timeAgo(status.last_run)})</span>
          </div>
        )}

        {/* Next run */}
        {status.next_run && !isHalted && (
          <div className="text-xs text-secondary">
            <span className="text-muted">Next:</span>{" "}
            {formatNextRun(status.next_run)}
          </div>
        )}

        {/* Total trades */}
        <div className="text-xs text-secondary">
          <span className="text-muted">Trades:</span> {status.total_trades} executed
        </div>
      </div>

      {/* Recent settings changes */}
      {status.recent_changes.length > 0 && (
        <div className="mt-3 border-t border-border/50 pt-2">
          <p className="text-[10px] text-muted mb-1">Recent changes:</p>
          <div className="flex flex-wrap gap-2">
            {status.recent_changes.slice(0, 3).map((c, i) => (
              <span
                key={i}
                className="rounded bg-card-alt px-2 py-0.5 text-[10px] text-secondary"
              >
                {c.action.replace(/_/g, " ")} · {timeAgo(c.timestamp)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
