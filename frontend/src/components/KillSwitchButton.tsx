"use client";

import { useState } from "react";
import { activateKillSwitch, deactivateKillSwitch } from "@/lib/api";
import ConfirmModal from "./ConfirmModal";

interface KillSwitchButtonProps {
  isActive: boolean;
  onToggled: () => void;
}

export default function KillSwitchButton({
  isActive,
  onToggled,
}: KillSwitchButtonProps) {
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      if (isActive) {
        await deactivateKillSwitch();
      } else {
        await activateKillSwitch();
      }
      onToggled();
    } catch (err) {
      console.error("Kill switch toggle failed:", err);
    } finally {
      setLoading(false);
      setShowModal(false);
    }
  }

  if (isActive) {
    return (
      <>
        <div className="flex items-center justify-between rounded-xl border border-neg/30 bg-neg/10 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="h-3 w-3 animate-pulse rounded-full bg-neg" />
            <span className="font-semibold text-neg">
              Kill Switch Active — All Trading Halted
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
          message="This will deactivate the kill switch and allow the bot to place orders again. Are you sure?"
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
        {loading ? "Activating..." : "KILL SWITCH"}
      </button>

      <ConfirmModal
        open={showModal}
        title="Activate Kill Switch"
        message="This will immediately halt ALL trading activity. The bot will not place any orders until you resume trading. Are you sure?"
        confirmLabel="Yes, halt all trading"
        onConfirm={handleConfirm}
        onCancel={() => setShowModal(false)}
      />
    </>
  );
}
