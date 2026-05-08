"use client";

import { useEffect, useState } from "react";
import { getBotStatus, BotStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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

    const interval = setInterval(() => {
      getBotStatus().then(setStatus).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [user]);

  if (!status) return null;

  // Portfolio-only model: "halted" means no portfolio is currently active.
  const isHalted = status.active_portfolios === 0;

  return (
    <div className="bz-glass mb-6 p-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              isHalted ? "bg-neg" : "bg-pos animate-pulse"
            }`}
          />
          <span
            className={`text-sm font-semibold ${
              isHalted ? "text-neg" : "text-pos"
            }`}
          >
            {isHalted ? "All Portfolios Halted" : "Bot Active"}
          </span>
        </div>

        <div className="text-xs text-secondary">
          <span className="text-muted">Schedule:</span>{" "}
          {status.frequency}/day ({status.schedule_times.join(", ")})
        </div>

        <div className="text-xs text-secondary">
          <span className="text-muted">Portfolios:</span>{" "}
          {status.active_portfolios} active / {status.total_portfolios} total
        </div>

        {status.last_run && (
          <div className="text-xs text-secondary">
            <span className="text-muted">Last:</span>{" "}
            {status.last_action?.toUpperCase()} {status.last_ticker}{" "}
            <span className="text-muted">({timeAgo(status.last_run)})</span>
          </div>
        )}

        {status.next_run && !isHalted && (
          <div className="text-xs text-secondary">
            <span className="text-muted">Next:</span>{" "}
            {formatNextRun(status.next_run)}
          </div>
        )}

        <div className="text-xs text-secondary">
          <span className="text-muted">Trades:</span> {status.total_trades} executed
        </div>
      </div>
    </div>
  );
}
