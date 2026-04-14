"use client";

import { changelog } from "@/data/changelog";
import { useHashScroll } from "@/lib/useHashScroll";
import CrossLink from "@/components/CrossLink";

const TYPE_STYLES: Record<string, string> = {
  feat: "bg-blue-900/30 text-blue-400",
  fix: "bg-red-900/30 text-red-400",
  docs: "bg-amber-900/30 text-amber-400",
  perf: "bg-emerald-900/30 text-emerald-400",
  refactor: "bg-purple-900/30 text-purple-400",
  security: "bg-yellow-900/30 text-yellow-400",
};

const totalChanges = changelog.reduce((sum, e) => sum + e.changes.length, 0);

export default function ChangelogPage() {
  useHashScroll();

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-primary">Changelog</h1>
        <p className="mt-1 text-sm text-muted">
          {changelog.length} releases, {totalChanges} changes — latest v{changelog[0].version}
        </p>
      </div>

      <div className="space-y-10">
        {changelog.map((entry) => (
          <div
            key={entry.version}
            id={`v${entry.version}`}
            className="border-l-2 border-border pl-6"
          >
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-primary">v{entry.version}</h2>
              <time className="text-sm text-muted">{entry.date}</time>
              {entry.roadmapLink && (
                <CrossLink type="roadmap" href={entry.roadmapLink} />
              )}
            </div>
            <ul className="mt-4 space-y-2">
              {entry.changes.map((change, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className={`mt-0.5 shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${TYPE_STYLES[change.type]}`}
                  >
                    {change.type}
                  </span>
                  <span className="text-sm text-secondary">{change.title}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
