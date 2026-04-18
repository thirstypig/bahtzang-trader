"use client";

import { useEffect, useState } from "react";
import { getPortfolio, getTrades } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Balance, Position, Trade } from "@/lib/types";
import PortfolioCard from "@/components/PortfolioCard";
import DecisionCard from "@/components/DecisionCard";
import dynamic from "next/dynamic";
import BotStatusBanner from "@/components/BotStatusBanner";
import Spinner from "@/components/Spinner";
import Tip from "@/components/Tip";

const AllocationChart = dynamic(() => import("@/components/AllocationChart"), { ssr: false });
const ValueChart = dynamic(() => import("@/components/ValueChart"), { ssr: false });

export default function DashboardPage() {
  const { user } = useAuth();
  const [positions, setPositions] = useState<Position[]>([]);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    async function load() {
      try {
        const [portfolio, tradeHistory] = await Promise.all([
          getPortfolio(),
          getTrades(100),
        ]);
        setPositions(portfolio.positions);
        setBalance(portfolio.balance);
        setTrades(tradeHistory);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [user]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="rounded-xl border border-red-900/50 bg-red-950/20 p-6">
          <p className="text-red-400">{error}</p>
          <p className="mt-2 text-sm text-muted">
            Make sure the backend is running at{" "}
            {process.env.NEXT_PUBLIC_API_URL || "http://localhost:4060"}
          </p>
        </div>
      </div>
    );
  }

  const lastDecision = trades.length > 0 ? trades[0] : null;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-primary">Dashboard</h1>
          <Tip text="This is your home base. It shows your current portfolio value, what the AI decided to do most recently, and how your money is allocated across stocks." />
        </div>
        <p className="mt-1 text-sm text-muted">
          Real-time portfolio overview and AI trading decisions
        </p>
      </div>

      <BotStatusBanner />

      <div className="grid gap-6 lg:grid-cols-2">
        <PortfolioCard balance={balance} positions={positions} />
        <DecisionCard trade={lastDecision} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <AllocationChart positions={positions} balance={balance} />
        <ValueChart trades={trades} />
      </div>
    </div>
  );
}
