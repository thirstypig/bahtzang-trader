"use client";

import { useState } from "react";
import { todos, Todo } from "@/data/todos";

const STATUS_STYLES = {
  todo: { dot: "bg-zinc-500", text: "text-zinc-400", label: "To Do" },
  "in-progress": { dot: "bg-blue-500", text: "text-blue-400", label: "In Progress" },
  done: { dot: "bg-emerald-500", text: "text-emerald-400", label: "Done" },
};

const PRIORITY_STYLES = {
  urgent: "bg-red-900/40 text-red-400 border-red-800",
  high: "bg-amber-900/30 text-amber-400 border-amber-800",
  medium: "bg-blue-900/30 text-blue-400 border-blue-800",
  low: "bg-zinc-800 text-zinc-500 border-zinc-700",
};

const CATEGORY_STYLES: Record<string, string> = {
  setup: "text-emerald-400",
  trading: "text-blue-400",
  risk: "text-red-400",
  feature: "text-purple-400",
  research: "text-amber-400",
};

type FilterStatus = "all" | "todo" | "in-progress" | "done";
type FilterCategory = "all" | Todo["category"];

export default function TodosPage() {
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [filterCategory, setFilterCategory] = useState<FilterCategory>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = todos.filter((t) => {
    if (filterStatus !== "all" && t.status !== filterStatus) return false;
    if (filterCategory !== "all" && t.category !== filterCategory) return false;
    return true;
  });

  const counts = {
    total: todos.length,
    todo: todos.filter((t) => t.status === "todo").length,
    inProgress: todos.filter((t) => t.status === "in-progress").length,
    done: todos.filter((t) => t.status === "done").length,
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">To-Do List</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Tasks to get the trading bot live and running
        </p>
      </div>

      {/* Summary */}
      <div className="mb-6 grid grid-cols-4 gap-3">
        {[
          { label: "Total", value: counts.total, color: "text-white" },
          { label: "To Do", value: counts.todo, color: "text-zinc-400" },
          { label: "In Progress", value: counts.inProgress, color: "text-blue-400" },
          { label: "Done", value: counts.done, color: "text-emerald-400" },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-center">
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-[10px] text-zinc-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-2">
        <FilterGroup
          label="Status"
          options={["all", "todo", "in-progress", "done"]}
          value={filterStatus}
          onChange={(v) => setFilterStatus(v as FilterStatus)}
        />
        <div className="mx-2 w-px bg-zinc-800" />
        <FilterGroup
          label="Category"
          options={["all", "setup", "trading", "risk", "feature", "research"]}
          value={filterCategory}
          onChange={(v) => setFilterCategory(v as FilterCategory)}
        />
      </div>

      {/* Task List */}
      <div className="space-y-2">
        {filtered.map((todo) => {
          const statusStyle = STATUS_STYLES[todo.status];
          const expanded = expandedId === todo.id;
          return (
            <div
              key={todo.id}
              className="rounded-xl border border-zinc-800 bg-zinc-900 transition-colors hover:border-zinc-700"
            >
              <button
                onClick={() => setExpandedId(expanded ? null : todo.id)}
                className="flex w-full items-center gap-3 px-5 py-4 text-left"
              >
                <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${statusStyle.dot}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white truncate">
                      {todo.title}
                    </span>
                    <span
                      className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase ${PRIORITY_STYLES[todo.priority]}`}
                    >
                      {todo.priority}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className={`text-[10px] font-medium uppercase ${CATEGORY_STYLES[todo.category]}`}>
                      {todo.category}
                    </span>
                    <span className="text-[10px] text-zinc-600">
                      Added {todo.addedDate}
                    </span>
                    {todo.dueDate && (
                      <span className="text-[10px] text-amber-500">
                        Due {todo.dueDate}
                      </span>
                    )}
                  </div>
                </div>
                <span className={`shrink-0 text-xs ${statusStyle.text}`}>
                  {statusStyle.label}
                </span>
                <svg
                  className={`h-4 w-4 shrink-0 text-zinc-600 transition-transform ${expanded ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expanded && (todo.description || todo.steps) && (
                <div className="border-t border-zinc-800 px-5 py-3">
                  {todo.description && (
                    <p className="text-sm text-zinc-400 leading-relaxed">
                      {todo.description}
                    </p>
                  )}
                  {todo.steps && (
                    <ol className="mt-3 space-y-1.5">
                      {todo.steps.map((step, i) => (
                        <li key={i} className="flex gap-2.5 text-sm">
                          <span className="shrink-0 text-xs font-mono text-zinc-600 mt-0.5 w-5 text-right">
                            {i + 1}.
                          </span>
                          <span className="text-zinc-400">{step}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                  {todo.completedDate && (
                    <p className="mt-2 text-xs text-emerald-600">
                      Completed {todo.completedDate}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center">
            <p className="text-zinc-500">No tasks match filters</p>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      <span className="mr-1 text-[10px] text-zinc-600">{label}:</span>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={`rounded px-2 py-1 text-[11px] font-medium transition-colors ${
            value === opt
              ? "bg-zinc-700 text-white"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          {opt === "in-progress" ? "In Progress" : opt.charAt(0).toUpperCase() + opt.slice(1)}
        </button>
      ))}
    </div>
  );
}
