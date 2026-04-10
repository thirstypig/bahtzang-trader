"use client";

import { changelog } from "@/data/changelog";

const TYPE_STYLES: Record<string, string> = {
  feat: "bg-blue-900/30 text-blue-400",
  fix: "bg-red-900/30 text-red-400",
  docs: "bg-amber-900/30 text-amber-400",
  perf: "bg-emerald-900/30 text-emerald-400",
  refactor: "bg-purple-900/30 text-purple-400",
};

export default function ChangelogPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Changelog</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Latest updates and improvements
        </p>
      </div>

      <div className="space-y-10">
        {changelog.map((entry) => (
          <div key={entry.version} className="border-l-2 border-zinc-800 pl-6">
            <div className="flex items-baseline gap-3">
              <h2 className="text-xl font-bold text-white">v{entry.version}</h2>
              <time className="text-sm text-zinc-500">{entry.date}</time>
            </div>
            <ul className="mt-4 space-y-2">
              {entry.changes.map((change, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className={`mt-0.5 shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${TYPE_STYLES[change.type]}`}
                  >
                    {change.type}
                  </span>
                  <span className="text-sm text-zinc-300">{change.title}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
