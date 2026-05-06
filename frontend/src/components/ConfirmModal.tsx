"use client";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  confirmClassName?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  confirmClassName = "bg-neg hover:opacity-90",
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/40" onClick={onCancel} />
      <div className="bz-glass-strong relative z-10 w-full max-w-md p-6">
        <h3 className="text-lg font-semibold text-primary">{title}</h3>
        <p className="mt-2 text-sm text-secondary">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="rounded-lg border border-border-strong px-4 py-2 text-sm font-medium text-secondary transition-colors hover:bg-card-alt"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-primary transition-colors ${confirmClassName}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
