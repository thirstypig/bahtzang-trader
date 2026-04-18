import { roadmapItems, RoadmapItem } from "@/data/roadmap";
import HashScroll from "@/components/HashScroll";

const STATUS_CONFIG = {
  planned: { label: "Planned", dot: "bg-muted" },
  "in-progress": { label: "In Progress", dot: "bg-blue-500" },
  done: { label: "Done", dot: "bg-accent" },
};

const PRIORITY_BADGE: Record<string, string> = {
  high: "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400",
  medium: "bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400",
  low: "bg-card-alt text-muted",
};

function Column({ status, items }: { status: keyof typeof STATUS_CONFIG; items: RoadmapItem[] }) {
  const config = STATUS_CONFIG[status];
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <div className="mb-4 flex items-center gap-2">
        <div className={`h-2.5 w-2.5 rounded-full ${config.dot}`} />
        <h2 className="text-sm font-semibold text-primary">{config.label}</h2>
        <span className="ml-auto text-xs text-muted">{items.length}</span>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.id}
            id={item.id}
            className="rounded-lg border border-border bg-surface p-4 transition-colors hover:border-border-strong"
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-medium text-primary">{item.title}</h3>
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${PRIORITY_BADGE[item.priority]}`}
              >
                {item.priority}
              </span>
            </div>
            <p className="mt-1.5 text-xs text-muted">{item.description}</p>
            <p className="mt-2 text-[10px] text-muted">{item.phase}</p>
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
      <HashScroll />
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-primary">Roadmap</h1>
        <p className="mt-1 text-sm text-muted">
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
