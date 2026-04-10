"use client";

import { roadmapItems, RoadmapItem } from "@/data/roadmap";

const STATUS_CONFIG = {
  planned: { label: "Planned", bg: "bg-zinc-800", text: "text-zinc-400", dot: "bg-zinc-500" },
  "in-progress": { label: "In Progress", bg: "bg-blue-900/30", text: "text-blue-400", dot: "bg-blue-500" },
  done: { label: "Done", bg: "bg-emerald-900/30", text: "text-emerald-400", dot: "bg-emerald-500" },
};

const PRIORITY_BADGE: Record<string, string> = {
  high: "bg-red-900/30 text-red-400",
  medium: "bg-amber-900/30 text-amber-400",
  low: "bg-zinc-800 text-zinc-500",
};

function Column({ status, items }: { status: string; items: RoadmapItem[] }) {
  const config = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG];
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <div className="mb-4 flex items-center gap-2">
        <div className={`h-2.5 w-2.5 rounded-full ${config.dot}`} />
        <h2 className="text-sm font-semibold text-white">{config.label}</h2>
        <span className="ml-auto text-xs text-zinc-500">{items.length}</span>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 transition-colors hover:border-zinc-700"
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-medium text-white">{item.title}</h3>
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${PRIORITY_BADGE[item.priority]}`}
              >
                {item.priority}
              </span>
            </div>
            <p className="mt-1.5 text-xs text-zinc-500">{item.description}</p>
            <p className="mt-2 text-[10px] text-zinc-600">{item.phase}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RoadmapPage() {
  const grouped = {
    "in-progress": roadmapItems.filter((i) => i.status === "in-progress"),
    planned: roadmapItems.filter((i) => i.status === "planned"),
    done: roadmapItems.filter((i) => i.status === "done"),
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Roadmap</h1>
        <p className="mt-1 text-sm text-zinc-500">
          What&apos;s being built, what&apos;s coming next
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Column status="in-progress" items={grouped["in-progress"]} />
        <Column status="planned" items={grouped.planned} />
        <Column status="done" items={grouped.done} />
      </div>
    </div>
  );
}
