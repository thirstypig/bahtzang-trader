"use client";

import { useEffect, useRef, useState } from "react";
import { getTodos, createTodo, updateTodo, deleteTodo, TodoTask } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import HashScroll from "@/components/HashScroll";
import CrossLink from "@/components/CrossLink";
import Spinner from "@/components/Spinner";

const STATUS_ORDER: TodoTask["status"][] = ["not_started", "in_progress", "done"];
const STATUS_STYLES: Record<string, { dot: string; text: string; label: string }> = {
  not_started: { dot: "bg-zinc-500", text: "text-secondary", label: "To Do" },
  in_progress: { dot: "bg-blue-500", text: "text-blue-400", label: "In Progress" },
  done: { dot: "bg-emerald-500", text: "text-emerald-400", label: "Done" },
};

const PRIORITY_STYLES: Record<string, string> = {
  p0: "bg-red-900/40 text-red-400 border-red-800",
  p1: "bg-amber-900/30 text-amber-400 border-amber-800",
  p2: "bg-blue-900/30 text-blue-400 border-blue-800",
  p3: "bg-card-alt text-muted border-border-strong",
};

const CATEGORY_STYLES: Record<string, string> = {
  "analytics-setup": "text-emerald-400",
  infrastructure: "text-blue-400",
  "trading-brain": "text-purple-400",
  "risk-management": "text-red-400",
  content: "text-amber-400",
  "code-quality": "text-secondary",
};

type FilterStatus = "all" | "active" | "done";

export default function TodosPage() {
  const { user } = useAuth();
  const [todos, setTodos] = useState<TodoTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterStatus>("active");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    if (!user) return;
    getTodos()
      .then(setTodos)
      .catch(() => setTodos([]))
      .finally(() => setLoading(false));
  }, [user]);

  const filtered = todos.filter((t) => {
    if (filter === "active") return t.status !== "done";
    if (filter === "done") return t.status === "done";
    return true;
  });

  const grouped = filtered.reduce<Record<string, TodoTask[]>>((acc, t) => {
    (acc[t.category] ??= []).push(t);
    return acc;
  }, {});

  const sortedCategories = Object.keys(grouped).sort((a, b) => {
    const aPriority = Math.min(...grouped[a].map((t) => parseInt(t.priority[1])));
    const bPriority = Math.min(...grouped[b].map((t) => parseInt(t.priority[1])));
    return aPriority - bPriority;
  });

  async function handleStatusCycle(todo: TodoTask) {
    const nextIdx = (STATUS_ORDER.indexOf(todo.status) + 1) % STATUS_ORDER.length;
    const nextStatus = STATUS_ORDER[nextIdx];
    const prevStatus = todo.status;

    setTodos((prev) =>
      prev.map((t) => (t.id === todo.id ? { ...t, status: nextStatus } : t))
    );
    try {
      await updateTodo(todo.id, { status: nextStatus });
    } catch {
      setTodos((prev) =>
        prev.map((t) => (t.id === todo.id ? { ...t, status: prevStatus } : t))
      );
    }
  }

  async function handleAddTask(task: Partial<TodoTask>) {
    try {
      const created = await createTodo(task);
      setTodos((prev) => [created, ...prev]);
      setShowAddForm(false);
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  }

  async function handleDelete(id: string) {
    setTodos((prev) => prev.filter((t) => t.id !== id));
    try {
      await deleteTodo(id);
    } catch {
      const fresh = await getTodos();
      setTodos(fresh);
    }
  }

  const totalDone = todos.filter((t) => t.status === "done").length;

  if (!user) return null;
  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <HashScroll />
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-primary">To-Do List</h1>
        <p className="mt-1 text-sm text-muted">
          {totalDone}/{todos.length} tasks done across {Object.keys(grouped).length} categories
        </p>
      </div>

      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-1">
          {(["all", "active", "done"] as FilterStatus[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                filter === f ? "bg-card-alt text-primary" : "text-muted hover:text-secondary"
              }`}
            >
              {f === "active" ? "Active" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-primary hover:bg-emerald-700"
        >
          + Add Task
        </button>
      </div>

      {showAddForm && (
        <AddTaskForm onAdd={handleAddTask} onCancel={() => setShowAddForm(false)} />
      )}

      <div className="space-y-4">
        {sortedCategories.map((category) => (
          <CategorySection
            key={category}
            category={category}
            items={grouped[category]}
            expandedId={expandedId}
            onToggleExpand={(id) => setExpandedId(expandedId === id ? null : id)}
            onStatusCycle={handleStatusCycle}
            onDelete={handleDelete}
          />
        ))}
        {sortedCategories.length === 0 && (
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <p className="text-muted">No tasks match filter</p>
          </div>
        )}
      </div>
    </div>
  );
}

function CategorySection({
  category,
  items,
  expandedId,
  onToggleExpand,
  onStatusCycle,
  onDelete,
}: {
  category: string;
  items: TodoTask[];
  expandedId: string | null;
  onToggleExpand: (id: string) => void;
  onStatusCycle: (todo: TodoTask) => void;
  onDelete: (id: string) => void;
}) {
  const done = items.filter((t) => t.status === "done").length;
  const pct = items.length > 0 ? Math.round((done / items.length) * 100) : 0;
  const categoryColor = CATEGORY_STYLES[category] || "text-secondary";

  return (
    <details open>
      <summary className="flex cursor-pointer select-none list-none items-center gap-3 rounded-lg border border-border bg-card px-5 py-3 hover:border-border-strong">
        <span className={`text-xs font-semibold uppercase tracking-wider ${categoryColor}`}>
          {category.replace(/-/g, " ")}
        </span>
        <span className="text-xs text-muted">
          {done}/{items.length}
        </span>
        <div className="ml-auto h-1.5 w-24 overflow-hidden rounded-full bg-card-alt">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </summary>
      <div className="mt-2 space-y-2 pl-2">
        {items.map((todo) => (
          <TodoRow
            key={todo.id}
            todo={todo}
            expanded={expandedId === todo.id}
            onToggleExpand={() => onToggleExpand(todo.id)}
            onStatusCycle={() => onStatusCycle(todo)}
            onDelete={() => onDelete(todo.id)}
          />
        ))}
      </div>
    </details>
  );
}

function TodoRow({
  todo,
  expanded,
  onToggleExpand,
  onStatusCycle,
  onDelete,
}: {
  todo: TodoTask;
  expanded: boolean;
  onToggleExpand: () => void;
  onStatusCycle: () => void;
  onDelete: () => void;
}) {
  const statusStyle = STATUS_STYLES[todo.status] || STATUS_STYLES.not_started;

  return (
    <div
      id={todo.id}
      className="rounded-xl border border-border bg-card transition-colors hover:border-border-strong"
    >
      <button
        onClick={onToggleExpand}
        aria-expanded={expanded}
        aria-controls={`details-${todo.id}`}
        className="flex w-full items-center gap-3 px-5 py-3 text-left"
      >
        <span
          onClick={(e) => {
            e.stopPropagation();
            onStatusCycle();
          }}
          className={`flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all hover:ring-1 hover:ring-zinc-600 ${statusStyle.text}`}
          title="Click to change status"
        >
          <span className={`h-2 w-2 rounded-full ${statusStyle.dot}`} />
          {statusStyle.label}
        </span>

        <span className="min-w-0 flex-1 truncate text-sm font-medium text-primary">
          {todo.title}
        </span>

        <span
          className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase ${PRIORITY_STYLES[todo.priority]}`}
        >
          {todo.priority}
        </span>

        <svg
          className={`h-4 w-4 shrink-0 text-muted transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div id={`details-${todo.id}`} className="border-t border-border px-5 py-3">
          <div className="flex items-center gap-3 text-[10px] text-muted">
            {todo.owner && <span>@{todo.owner}</span>}
            {todo.target_date && <span>Due {todo.target_date}</span>}
            <span>Created {todo.created_at.split("T")[0]}</span>
          </div>

          {todo.description && (
            <p className="mt-2 text-sm leading-relaxed text-secondary">{todo.description}</p>
          )}

          {todo.steps && todo.steps.length > 0 && (
            <ol className="mt-3 space-y-1.5">
              {todo.steps.map((step, i) => (
                <li key={i} className="flex gap-2.5 text-sm">
                  <span className="mt-0.5 w-5 shrink-0 text-right font-mono text-xs text-muted">
                    {i + 1}.
                  </span>
                  <span className="text-secondary">{step}</span>
                </li>
              ))}
            </ol>
          )}

          {(todo.roadmap_link || todo.concept_link) && (
            <div className="mt-3 flex items-center gap-2 border-t border-border/50 pt-3">
              <span className="shrink-0 text-[10px] text-muted">Related:</span>
              <div className="flex flex-wrap gap-1.5">
                {todo.roadmap_link && <CrossLink type="roadmap" href={todo.roadmap_link} />}
                {todo.concept_link && <CrossLink type="concept" href={todo.concept_link} />}
              </div>
            </div>
          )}

          <div className="mt-3 border-t border-border/50 pt-3">
            <button onClick={onDelete} className="text-[10px] text-red-500 hover:text-red-400">
              Delete task
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function AddTaskForm({
  onAdd,
  onCancel,
}: {
  onAdd: (task: Partial<TodoTask>) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("content");
  const [priority, setPriority] = useState<TodoTask["priority"]>("p2");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSubmit() {
    if (!title.trim()) return;
    onAdd({ title: title.trim(), category, priority, owner: "jimmy" });
  }

  return (
    <div className="mb-4 rounded-xl border border-emerald-800/50 bg-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <div className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
        <span className="text-sm font-medium text-emerald-400">New Task</span>
      </div>
      <input
        ref={inputRef}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Task title..."
        className="w-full rounded-lg border border-border-strong bg-card-alt px-3 py-2 text-sm text-primary placeholder-zinc-500 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSubmit();
          if (e.key === "Escape") onCancel();
        }}
      />
      <div className="mt-3 flex items-center gap-3">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-border-strong bg-card-alt px-2 py-1.5 text-xs text-secondary"
        >
          {Object.keys(CATEGORY_STYLES).map((c) => (
            <option key={c} value={c}>
              {c.replace(/-/g, " ")}
            </option>
          ))}
        </select>
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as TodoTask["priority"])}
          className="rounded-lg border border-border-strong bg-card-alt px-2 py-1.5 text-xs text-secondary"
        >
          <option value="p0">P0 - Critical</option>
          <option value="p1">P1 - High</option>
          <option value="p2">P2 - Medium</option>
          <option value="p3">P3 - Low</option>
        </select>
        <div className="ml-auto flex gap-2">
          <button onClick={onCancel} className="rounded-lg px-3 py-1.5 text-xs text-secondary hover:text-primary">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-primary hover:bg-emerald-700"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
