"use client";

import { useState } from "react";
import { activateKillSwitch } from "@/lib/api";
import ConfirmModal from "./ConfirmModal";

interface KillSwitchButtonProps {
  isActive: boolean;
  onActivated: () => void;
}

export default function KillSwitchButton({
  isActive,
  onActivated,
}: KillSwitchButtonProps) {
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await activateKillSwitch();
      onActivated();
    } catch (err) {
      console.error("Kill switch failed:", err);
    } finally {
      setLoading(false);
      setShowModal(false);
    }
  }

  if (isActive) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-red-900/50 bg-red-950/30 px-6 py-4">
        <div className="h-3 w-3 animate-pulse rounded-full bg-red-500" />
        <span className="font-semibold text-red-400">
          Kill Switch Active — All Trading Halted
        </span>
      </div>
    );
  }

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        disabled={loading}
        className="rounded-xl bg-red-600 px-8 py-4 text-lg font-bold text-white shadow-lg shadow-red-900/30 transition-all hover:bg-red-700 hover:shadow-red-900/50 active:scale-95 disabled:opacity-50"
      >
        {loading ? "Activating..." : "KILL SWITCH"}
      </button>

      <ConfirmModal
        open={showModal}
        title="Activate Kill Switch"
        message="This will immediately halt ALL trading activity. The bot will not place any orders until the kill switch is manually deactivated. Are you sure?"
        confirmLabel="Yes, halt all trading"
        onConfirm={handleConfirm}
        onCancel={() => setShowModal(false)}
      />
    </>
  );
}
