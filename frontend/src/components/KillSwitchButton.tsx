"use client";

import { useState } from "react";
import { updatePortfolio } from "@/lib/api";
import ConfirmModal from "./ConfirmModal";

interface KillSwitchButtonProps {
  portfolioId: number;
  isActive: boolean;
  onToggled: () => void;
}

/**
 * Per-portfolio kill switch — toggles Portfolio.is_active.
 *
 * Portfolio-only model: there is no global kill switch. Each portfolio
 * has its own. To halt EVERYTHING, the user toggles each active portfolio.
 */
export default function KillSwitchButton({
  portfolioId,
  isActive,
  onToggled,
}: KillSwitchButtonProps) {
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await updatePortfolio(portfolioId, { is_active: !isActive });
      onToggled();
    } catch (err) {
      console.error("Portfolio active toggle failed:", err);
    } finally {
      setLoading(false);
      setShowModal(false);
    }
  }

  if (!isActive) {
    return (
      <>
        <div className="flex items-center justify-between rounded-xl border border-neg/30 bg-neg/10 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="h-3 w-3 animate-pulse rounded-full bg-neg" />
            <span className="font-semibold text-neg">
              Portfolio Halted — Trading Paused
            </span>
          </div>
          <button
            onClick={() => setShowModal(true)}
            disabled={loading}
            className="rounded-lg border border-border-strong bg-card-alt px-4 py-2 text-sm font-medium text-secondary transition-all hover:bg-border-strong disabled:opacity-50"
          >
            {loading ? "Resuming..." : "Resume Trading"}
          </button>
        </div>

        <ConfirmModal
          open={showModal}
          title="Resume Trading"
          message="This will reactivate the portfolio and allow it to place orders again. Are you sure?"
          confirmLabel="Yes, resume trading"
          onConfirm={handleConfirm}
          onCancel={() => setShowModal(false)}
        />
      </>
    );
  }

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        disabled={loading}
        className="rounded-xl bg-neg px-8 py-4 text-lg font-bold text-white shadow-lg shadow-neg/30 transition-all hover:opacity-90 hover:shadow-neg/50 active:scale-95 disabled:opacity-50"
      >
        {loading ? "Halting..." : "HALT PORTFOLIO"}
      </button>

      <ConfirmModal
        open={showModal}
        title="Halt Portfolio"
        message="This will immediately halt this portfolio's trading. It will not place any orders until you resume. Are you sure?"
        confirmLabel="Yes, halt this portfolio"
        onConfirm={handleConfirm}
        onCancel={() => setShowModal(false)}
      />
    </>
  );
}
