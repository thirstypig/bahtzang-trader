---
title: "Admin System: Interconnected Todo + Roadmap + Concepts + Changelog"
type: feat
status: active
date: 2026-04-12
deepened: 2026-04-12
---

# Admin System: Interconnected Todo + Roadmap + Concepts + Changelog

## Enhancement Summary

**Deepened on:** 2026-04-12
**Sections enhanced:** 6
**Research agents used:** 3 (FastAPI file CRUD, admin UI patterns, cross-linking patterns)

### Key Improvements
1. **Backend persistence** — `asyncio.Lock` (not threading.Lock) for FastAPI's async model, atomic writes via `tempfile.mkstemp` + `os.replace`, three Pydantic models (Create/Update/Item)
2. **Collapsible sections** — use native `<details>/<summary>` for free keyboard accessibility + progress bars in summary row
3. **URL-based tabs** — `useSearchParams` + `router.replace` for shareable, refreshable tab state on Concepts page
4. **Cross-link system** — reusable `CrossLink` badge component, `useHashScroll` hook, CSS `scroll-margin-top` for fixed navbar offset
5. **Admin navigation** — shared `AdminNav` component imported on each page (not a route group layout)
6. **Status cycling** — optimistic UI with rollback on error, `e.stopPropagation()` for nested click handlers

### New Considerations Discovered
- Use `asyncio.Lock` for FastAPI (not `threading.Lock`) — async endpoints share a single event loop thread
- Railway Volume mount is a one-click persistence upgrade if JSON file loss becomes an issue
- URL-based tabs (`?tab=seo`) give free shareability and browser back/forward support
- `scroll-margin-top: 5rem` on `[id]` elements offsets anchors below the fixed navbar
- Next.js `<Link>` with hash fragments needs a `useHashScroll()` hook for client-rendered pages

---

## Overview

Build an interconnected 4-page admin section where **Todo is what to do NOW** (with exact steps), **Roadmap is WHERE we're going**, **Concepts is WHAT we're exploring**, and **Changelog is WHAT we shipped**. All pages cross-link to each other via anchor links and badge-links.

## Problem Statement

The existing admin pages (todo, roadmap, changelog) are static data files with no API persistence, no cross-linking, and no concepts page. Changes require code commits. The todo page has no "Add Task" functionality, no category grouping with progress bars, and no link to related roadmap sections or concepts.

## Existing State

| Page | Current | Target |
|------|---------|--------|
| `/todos` | Static `data/todos.ts`, 17 items, filter by status/category | API-backed, CRUD, grouped categories, cross-links |
| `/roadmap` | Static `data/roadmap.ts`, 3-column kanban | Enhanced with anchors, deferred status, cross-links |
| `/changelog` | Static `data/changelog.ts`, timeline layout | Add cross-links to todo/roadmap, stats header |
| `/concepts` | Does not exist | New page: tabbed layout with strategic/SEO/integrations/UX tabs |

---

## Phase 1: Backend — Todo API (FastAPI)

### New File: `backend/app/routes/todos.py`

Router with `prefix="/admin/todos"`, `tags=["admin"]`. All endpoints behind `Depends(require_auth)`.

```python
@router.get("", response_model=list[TodoItem])
async def list_todos(status: TodoStatus | None = None, user=Depends(require_auth))

@router.post("", response_model=TodoItem, status_code=201)
async def create_todo(body: TodoCreate, user=Depends(require_auth))

@router.patch("/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: UUID, body: TodoUpdate, user=Depends(require_auth))

@router.delete("/{todo_id}", status_code=204)
async def delete_todo(todo_id: UUID, user=Depends(require_auth))
```

### Research Insights: Persistence

**Use `asyncio.Lock`**, not `threading.Lock`. FastAPI's async endpoints share a single event loop thread — `threading.Lock` would block the entire event loop.

**Atomic writes** via `tempfile.mkstemp` (same directory) + `os.fsync` + `os.replace`:
```python
_lock = asyncio.Lock()

def _write_sync(todos: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, TODOS_FILE)  # Atomic on POSIX
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
```

Every mutation acquires the lock before reading, then writes before releasing — prevents TOCTOU races.

### Research Insights: ID Generation

Use **`uuid4()`** — stateless, no collision risk, no need to read file for max ID. Consistent with Supabase user IDs already in the codebase.

### Three Pydantic Models (Create / Update / Item)

```python
class TodoCreate(BaseModel):
    """Input for POST — only user-provided fields."""
    title: str = Field(..., min_length=1, max_length=200)
    category: str
    priority: str = Field(default="p2", pattern="^(p0|p1|p2|p3)$")
    description: str | None = None
    steps: list[str] | None = None
    roadmap_link: str | None = None
    concept_link: str | None = None
    target_date: str | None = None
    owner: str | None = None

class TodoUpdate(BaseModel):
    """Input for PATCH — all fields optional."""
    title: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = Field(None, pattern="^(not_started|in_progress|done)$")
    priority: str | None = Field(None, pattern="^(p0|p1|p2|p3)$")
    description: str | None = None
    steps: list[str] | None = None
    roadmap_link: str | None = None
    concept_link: str | None = None
    target_date: str | None = None
    owner: str | None = None

class TodoItem(BaseModel):
    """Full stored object — response model."""
    id: UUID
    title: str
    category: str
    status: str = "not_started"
    priority: str = "p2"
    owner: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    roadmap_link: str | None = None
    concept_link: str | None = None
    target_date: str | None = None
    created_at: str
    updated_at: str
```

**Why three models**: `TodoCreate` prevents client from setting `id`/`created_at`. `TodoUpdate` makes all fields Optional for PATCH. `TodoItem` is the full schema for storage + `response_model` (auto-generates OpenAPI docs).

### Research Insights: Railway Persistence

Railway's filesystem is ephemeral — `todo-tasks.json` is lost on every deploy. For admin task tracking this is acceptable (tasks can be reconstructed). Mitigations:

- **Seed on startup**: create file with empty `[]` if missing
- **Upgrade path**: Railway Volume mount (`/data`) — one-click in Railway dashboard, survives deploys
- **Env var**: `DATA_DIR = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", str(default_path)))`

### CORS Update

Add `PATCH` and `DELETE` to `allow_methods` in `main.py`:
```python
allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
```

### Data File: `backend/data/todo-tasks.json`

Seed with ~15 actionable tasks across 6 categories reflecting current project priorities.

### Initial Task Categories

| Category | Color | Example Tasks |
|----------|-------|-------|
| `analytics-setup` | emerald | Portfolio snapshots, equity curve, Sharpe ratio |
| `infrastructure` | blue | Slack webhook setup, Alpaca Data API migration |
| `trading-brain` | purple | pandas-ta indicators, sector rotation, CSV prompt |
| `risk-management` | red | Kelly criterion, circuit breakers, PDT compliance |
| `content` | amber | Populate concepts, update roadmap, documentation |
| `code-quality` | zinc | Test coverage, type safety, dead code cleanup |

---

## Phase 2: Frontend — Enhanced Todo Page

### Component: `frontend/src/app/todos/page.tsx` (rewrite)

### Research Insights: Collapsible Category Sections

Use **native `<details>/<summary>`** for collapse mechanism:
- Free keyboard support (Enter/Space to toggle)
- Screen readers announce "expanded"/"collapsed" automatically
- Progressive enhancement (works without JS)
- Less code than manual `aria-expanded`/`aria-controls`

```tsx
function CategorySection({ category, items }: Props) {
  const [open, setOpen] = useState(true);
  const done = items.filter(t => t.status === "done").length;
  const pct = Math.round((done / items.length) * 100);

  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="flex cursor-pointer items-center gap-3 rounded-lg
                          bg-zinc-900 px-5 py-3 list-none border border-zinc-800
                          hover:border-zinc-700 select-none">
        <ChevronIcon open={open} />
        <span className={`text-xs font-semibold uppercase ${CATEGORY_STYLES[category]}`}>
          {category}
        </span>
        <span className="text-xs text-zinc-500">{done}/{items.length}</span>
        <div className="ml-auto h-1.5 w-24 overflow-hidden rounded-full bg-zinc-800">
          <div className="h-full rounded-full bg-emerald-500 transition-all"
               style={{ width: `${pct}%` }} />
        </div>
      </summary>
      <div className="mt-2 space-y-2 pl-2">
        {items.map(todo => <TodoRow key={todo.id} todo={todo} />)}
      </div>
    </details>
  );
}
```

**Grouping logic:**
```tsx
const grouped = filtered.reduce<Record<string, TodoTask[]>>((acc, t) => {
  (acc[t.category] ??= []).push(t);
  return acc;
}, {});
```

### Research Insights: Status Cycling with Optimistic UI

Click status badge to cycle through states. Optimistic update with rollback on error:

```tsx
const STATUS_ORDER = ["not_started", "in_progress", "done"];

function StatusBadge({ todo }: { todo: TodoTask }) {
  const [status, setStatus] = useState(todo.status);
  const [saving, setSaving] = useState(false);

  async function cycleStatus(e: React.MouseEvent) {
    e.stopPropagation(); // Don't toggle parent collapse
    const nextIdx = (STATUS_ORDER.indexOf(status) + 1) % STATUS_ORDER.length;
    const nextStatus = STATUS_ORDER[nextIdx];
    const prevStatus = status;

    setStatus(nextStatus);  // Optimistic
    setSaving(true);
    try {
      await updateTodo(todo.id, { status: nextStatus });
    } catch {
      setStatus(prevStatus);  // Rollback
    } finally {
      setSaving(false);
    }
  }
  // ... render badge with dot + label + animate-pulse while saving
}
```

### Research Insights: Inline "Add Task" Form

Inline form slides open at top of task list (not a modal). Enter to submit, Escape to cancel:

```tsx
function AddTaskInline({ onAdd, onCancel }: Props) {
  const [title, setTitle] = useState("");
  return (
    <div className="rounded-xl border border-emerald-800/50 bg-zinc-900 p-5 mb-4">
      <input autoFocus value={title} onChange={e => setTitle(e.target.value)}
        placeholder="Task title..."
        className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm"
        onKeyDown={e => {
          if (e.key === "Enter" && title.trim()) onAdd({ title, ... });
          if (e.key === "Escape") onCancel();
        }} />
      {/* Category + priority selects + Add/Cancel buttons */}
    </div>
  );
}
```

### Layout

```
┌─────────────────────────────────────────────┐
│ [AdminNav: Todo | Roadmap | Concepts | ...] │
│                                             │
│ To-Do List                                  │
│ [All] [Active] [Done]      [+ Add Task]    │
│                                             │
│ ▾ Analytics Setup (2/5) ████░░░░░           │
│   ☐ Build portfolio snapshots       p1      │
│     → Roadmap: Portfolio Analytics          │
│   ☐ Add equity curve chart          p2      │
│                                             │
│ ▾ Infrastructure (1/3) ███░░░░░░░           │
│   ☑ Set up Slack webhook                    │
│   ☐ Migrate to Alpaca Data API              │
│                                             │
│ ▸ Trading Brain (collapsed)                 │
│ ▸ Risk Management (collapsed)               │
└─────────────────────────────────────────────┘
```

---

## Phase 3: Frontend — Concepts Page (NEW)

### Component: `frontend/src/app/concepts/page.tsx`

### Research Insights: URL-Based Tabs

Use `useSearchParams` for tab state — URL is the source of truth. Gives free shareability (`/concepts?tab=seo`), browser back/forward support, and survives page refresh:

```tsx
function useTabs(defaultTab = "strategic") {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const activeTab = searchParams.get("tab") || defaultTab;

  function setTab(tab: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return [activeTab, setTab] as const;
}
```

**Tab bar with ARIA accessibility** (W3C WAI-ARIA Tabs Pattern):
```tsx
<div role="tablist" aria-label="Concept categories" className="mt-6 flex border-b border-zinc-800">
  {TABS.map(tab => (
    <button key={tab.key} role="tab"
      id={`tab-${tab.key}`}
      aria-selected={activeTab === tab.key}
      aria-controls={`panel-${tab.key}`}
      onClick={() => setTab(tab.key)}
      className={`relative px-4 py-2.5 text-sm font-medium transition-colors
        ${activeTab === tab.key ? "text-white" : "text-zinc-500 hover:text-zinc-300"}`}>
      {tab.label}
      {activeTab === tab.key && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />
      )}
    </button>
  ))}
</div>
```

**Keyboard navigation**: Arrow keys move between tabs (optional enhancement).

### Tabs & Content

| Tab | Content |
|-----|---------|
| **Strategic** | Multi-model consensus, backtesting, options engine, crypto 24/7, social sentiment |
| **SEO Pages** | AI Trading Bot Guide, Claude for Trading, Paper Trading Tutorial |
| **Integrations** | Finnhub, TradingView, Alpaca Data API, Discord |
| **UX Mockups** | Mobile PWA, dark/light toggle, allocation sunburst |

Data in `frontend/src/data/concepts.ts` (static, like changelog).

---

## Phase 4: Frontend — Enhanced Changelog

1. Stats header: total releases, total changes, latest version
2. Cross-link badges on releases (using `CrossLink` component)
3. Add v0.7.0 entry with all code review + notification changes
4. Add "security" type badge (yellow-green)
5. Add `AdminNav` at top
6. Add `id={`v${entry.version}`}` on each release for anchor linking

---

## Phase 5: Enhanced Roadmap

1. Add `id={item.id}` and `scroll-mt-20` to each card for cross-linking
2. Add `AdminNav` at top
3. Add "deferred" status column (4 columns)
4. Update roadmap data to reflect completed phases
5. Add `CrossLink` badges on items that have related todos/concepts

---

## Phase 6: Shared Components & Cross-Linking

### Research Insights: Cross-Link Component

Reusable pill-shaped badge matching existing badge conventions:

```tsx
// frontend/src/components/CrossLink.tsx
const LINK_STYLES = {
  roadmap:   { bg: "bg-purple-900/30", text: "text-purple-400", label: "Roadmap" },
  todo:      { bg: "bg-zinc-800",      text: "text-zinc-400",   label: "Todo" },
  changelog: { bg: "bg-blue-900/30",   text: "text-blue-400",   label: "Changelog" },
  concept:   { bg: "bg-amber-900/30",  text: "text-amber-400",  label: "Concept" },
};

function CrossLink({ type, href, label }: Props) {
  return (
    <Link href={href}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5
                  text-[10px] font-medium hover:brightness-125 ${styles.bg} ${styles.text}`}>
      <ExternalLinkIcon className="h-2.5 w-2.5" />
      {label || styles.label}
    </Link>
  );
}
```

Cross-links shown inside expanded/detail views only (avoids clutter on collapsed cards). Prefix with "Related:" label.

### Research Insights: AdminNav Component

Shared navigation imported on each admin page (not a route group layout):

```tsx
// frontend/src/components/AdminNav.tsx
const ADMIN_LINKS = [
  { href: "/todos", label: "Todo" },
  { href: "/roadmap", label: "Roadmap" },
  { href: "/concepts", label: "Concepts" },
  { href: "/changelog", label: "Changelog" },
];

function AdminNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-6 flex items-center gap-1 border-b border-zinc-800 pb-3">
      {ADMIN_LINKS.map(link => (
        <Link key={link.href} href={link.href}
          className={`rounded-md px-3 py-1.5 text-xs font-medium ${
            pathname === link.href ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-300"
          }`}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
```

### Research Insights: Smooth Scroll + Fixed Navbar Offset

Add to `frontend/src/app/globals.css`:
```css
html { scroll-behavior: smooth; }
[id] { scroll-margin-top: 5rem; } /* 80px = navbar(64px) + 16px */
```

### Research Insights: useHashScroll Hook

Handle hash scrolling on client-rendered pages where target elements mount after navigation:

```tsx
// frontend/src/lib/useHashScroll.ts
export function useHashScroll() {
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash) return;
    const timeout = setTimeout(() => {
      document.getElementById(hash.slice(1))?.scrollIntoView({
        behavior: "smooth", block: "start"
      });
    }, 100);
    return () => clearTimeout(timeout);
  }, []);
}
```

Call on each page that's a cross-link target (Todos, Roadmap, Concepts, Changelog).

---

## Phase 7: Wiring & Registration

### Routing
Next.js App Router auto-routes — no changes needed except creating the `/concepts` directory.

### Navbar Update
Add "Concepts" to Admin section in `Navbar.tsx`:
```typescript
{ label: "Concepts", href: "/concepts" },
```

### Backend Registration
```python
# main.py
from app.routes import bot, guardrails, portfolio, todos, trades
app.include_router(todos.router)
```

---

## Acceptance Criteria

### Todo Page
- [ ] Tasks fetched from FastAPI backend (not static import)
- [ ] Tasks grouped by category with `<details>/<summary>` collapsible sections
- [ ] Progress bars showing done/total per category
- [ ] Inline "Add Task" form creates task via API
- [ ] Status cycling on badge click (optimistic + rollback)
- [ ] Cross-link badges to Roadmap/Concepts in expanded view
- [ ] Filter: All / Active (default) / Done
- [ ] Expanded view shows numbered steps
- [ ] `aria-expanded` and `aria-controls` on collapsible elements

### Concepts Page
- [ ] 4 URL-based tabs (`?tab=strategic|seo|integrations|ux`)
- [ ] Each concept has status badge and description
- [ ] Cross-links to related Todo items and Roadmap sections
- [ ] Populated with bahtzang-trader specific concepts
- [ ] ARIA tab roles (role="tablist", role="tab", role="tabpanel")
- [ ] Tabs survive page refresh and browser back/forward

### Changelog
- [ ] Stats header (total releases, total changes)
- [ ] Cross-link badges on releases
- [ ] v0.7.0 entry with code review + notification changes
- [ ] "security" type badge added
- [ ] `id` on each version for anchor linking

### Roadmap
- [ ] `id` + `scroll-mt-20` on each card for cross-linking
- [ ] Updated data reflecting completed phases
- [ ] AdminNav at top

### Cross-Linking
- [ ] `CrossLink` reusable component renders pill badges
- [ ] `AdminNav` component on every admin page with active state
- [ ] `useHashScroll` hook handles delayed-mount anchor scrolling
- [ ] CSS `scroll-margin-top` offsets anchors below navbar
- [ ] All cross-links use Next.js `<Link>` for client-side navigation

---

## Files to Create/Modify

### New Files (9)
| File | Description |
|------|-------------|
| `backend/app/routes/todos.py` | CRUD endpoints with asyncio.Lock + atomic JSON writes |
| `backend/data/todo-tasks.json` | Initial todo task data (~15 tasks) |
| `frontend/src/app/concepts/page.tsx` | New tabbed concepts page |
| `frontend/src/data/concepts.ts` | Concepts data (static) |
| `frontend/src/components/CrossLink.tsx` | Reusable cross-link badge |
| `frontend/src/components/AdminNav.tsx` | Shared admin page navigation |
| `frontend/src/lib/useHashScroll.ts` | Hash scroll hook for client pages |

### Modified Files (9)
| File | Changes |
|------|---------|
| `backend/app/main.py` | Register todos router, add PATCH/DELETE to CORS |
| `frontend/src/app/globals.css` | Add `scroll-behavior: smooth` + `scroll-margin-top` |
| `frontend/src/app/todos/page.tsx` | Full rewrite: API-backed, categories, progress bars |
| `frontend/src/app/roadmap/page.tsx` | Add anchors, AdminNav, deferred status |
| `frontend/src/app/changelog/page.tsx` | Add stats, cross-links, v0.7.0, security type |
| `frontend/src/data/roadmap.ts` | Update items to reflect current state |
| `frontend/src/data/changelog.ts` | Add v0.7.0, cross-link fields, security type |
| `frontend/src/lib/api.ts` | Add getTodos, createTodo, updateTodo, deleteTodo |
| `frontend/src/components/Navbar.tsx` | Add Concepts link to Admin group |

---

## Implementation Order

1. **Shared components**: `CrossLink.tsx`, `AdminNav.tsx`, `useHashScroll.ts`, `globals.css`
2. **Backend**: Create `todos.py` routes + `todo-tasks.json` with initial data
3. **Frontend API**: Add todo CRUD functions to `api.ts`
4. **Todo Page**: Rewrite with API, categories, progress bars, cross-links
5. **Concepts Page**: New page with tabs and populated data
6. **Changelog**: Add stats, cross-links, v0.7.0 entry
7. **Roadmap**: Add anchors, update data, add AdminNav
8. **Navbar**: Add Concepts link
9. **Test**: Verify all cross-links work, check ARIA accessibility

---

## Sources

- [FastAPI Concurrency and async/await](https://fastapi.tiangolo.com/async/)
- [Crash-safe JSON: atomic writes + recovery without a DB](https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic)
- [Railway Volumes documentation](https://docs.railway.com/reference/volumes)
- [W3C WAI-ARIA Tabs Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)
- [Harvard Digital Accessibility: Expandable Sections](https://accessibility.huit.harvard.edu/technique-expandable-sections)
- [CSS-Tricks: Fixed Headers and Jump Links — scroll-margin-top](https://css-tricks.com/fixed-headers-and-jump-links-the-solution-is-scroll-margin-top/)
- [Robin Wieruch: Search Params in Next.js for URL State](https://www.robinwieruch.de/next-search-params/)
- [Next.js Link Component (hash support)](https://nextjs.org/docs/app/api-reference/components/link)
- [Vercel/Next.js Issue #51721: Link smooth scroll](https://github.com/vercel/next.js/issues/51721)
- [React Aria: Disclosure Component](https://react-spectrum.adobe.com/react-aria/Disclosure.html)
