"use client";

interface TipProps {
  text: string;
  position?: "top" | "bottom" | "left" | "right";
}

export default function Tip({ text, position = "top" }: TipProps) {
  const positionClasses: Record<string, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <span className="group/tip relative inline-flex cursor-help">
      <svg
        className="h-3.5 w-3.5 text-muted transition-colors group-hover/tip:text-secondary"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4M12 8h.01" />
      </svg>
      <span
        className={`pointer-events-none absolute z-50 w-64 max-w-[calc(100vw-2rem)] rounded-lg border border-border-strong bg-card px-3 py-2 text-xs leading-relaxed text-secondary opacity-0 shadow-xl transition-opacity group-hover/tip:opacity-100 ${positionClasses[position]}`}
      >
        {text}
      </span>
    </span>
  );
}

export function SectionHeader({
  title,
  description,
  tip,
}: {
  title: string;
  description: string;
  tip?: string;
}) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold text-primary">{title}</h1>
        {tip && <Tip text={tip} />}
      </div>
      <p className="mt-1 text-sm text-muted">{description}</p>
    </div>
  );
}
