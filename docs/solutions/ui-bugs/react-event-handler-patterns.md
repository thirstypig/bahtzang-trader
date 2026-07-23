---
id: DOC-051
type: solution
status: active
phase: null
owner: james
tags: [frontend]
links: []
updated: 2026-05-15
severity: medium
component: "frontend/src/app/portfolios/page.tsx, frontend/src/components/TopNav.tsx"
---

# React Event Handler Patterns — Three Related Bugs

Three bugs found together during code review of the portfolio pause/resume feature. All involve
`useEffect` or async event handlers in React components.

## Bugs

### Bug 1 — Stale closure in optimistic state update

**Location:** `frontend/src/app/portfolios/page.tsx` — `handleToggleActive`

**Symptom:** If a background refresh or concurrent re-render updates the `portfolios` array between
when the handler is called and when the `await` resolves, the `setPortfolios(portfolios.map(...))` call
clobbers the newer state because it closed over the old array.

**Root cause:** React state setters that reference a state variable directly capture the value at
closure creation time. After any `await`, the event loop yields and re-renders may have replaced the
state the closure captured. The functional updater form receives the *current* state at the moment
React processes the update, bypassing the stale closure entirely.

```typescript
// BAD: `portfolios` captured at handler creation time; stale after await
const updated = await updatePortfolio(portfolio.id, { is_active: !portfolio.is_active });
setPortfolios(portfolios.map((p) =>
  p.id === portfolio.id ? { ...p, is_active: updated.is_active } : p
));

// GOOD: `prev` is the live state at the moment React processes the update
const updated = await updatePortfolio(portfolio.id, { is_active: !portfolio.is_active });
setPortfolios((prev) => prev.map((p) =>
  p.id === portfolio.id ? { ...p, is_active: updated.is_active } : p
));
```

**Rule of thumb:** If there is an `await` anywhere between the top of a handler and a `setState` call
that reads from array/object state, use the functional updater form.

---

### Bug 2 — Inconsistent click-outside patterns

**Locations:**
- `portfolios/page.tsx` uses `data-attribute + closest()`
- `TopNav.tsx` uses `useRef + contains()`

**Symptom:** No runtime bug today, but a maintenance trap. The `data-attribute + closest()` approach
introduces an implicit string contract between the event handler and the JSX. If the attribute is
renamed in one place but not the other, click-outside detection silently breaks with no TypeScript
error. The `closest()` approach also has a subtle scope issue — since every portfolio card has
`data-portfolio-menu`, clicking *any* card body while one menu is open registers as "inside" and
suppresses the close.

```typescript
// BAD (portfolios/page.tsx): implicit string contract, no type safety
//   ALSO: data-portfolio-menu is on every card, so clicking any card body
//   suppresses the close even if a different card's menu is open
useEffect(() => {
  if (!menuOpen) return;
  function close(e: MouseEvent) {
    if (!(e.target as Element).closest("[data-portfolio-menu]")) setMenuOpen(null);
  }
  document.addEventListener("mousedown", close);
  return () => document.removeEventListener("mousedown", close);
}, [menuOpen]);

// GOOD: ref ties directly to the element; no string contract
const menuRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  if (!menuOpen) return;
  function handleClickOutside(e: MouseEvent) {
    if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
      setMenuOpen(null);
    }
  }
  document.addEventListener("mousedown", handleClickOutside);
  return () => document.removeEventListener("mousedown", handleClickOutside);
}, [menuOpen]);

// JSX — attach the ref to the menu container; no data attribute needed
<div ref={menuRef}>...</div>
```

**Canonical pattern for this codebase:** Use `useRef + contains()`. It is already established in
`TopNav.tsx` (`navRef`), is the React docs convention, and is type-safe.

---

### Bug 3 — Unconditional click-outside listener (wrong dependency array)

**Location:** `frontend/src/components/TopNav.tsx` — profile dropdown effect

**Symptom:** The `mousedown` listener is attached on mount and never detaches until unmount (empty
`[]` dep array). For a nav component that is always mounted, this listener fires on every single
user interaction anywhere in the app, calling `setProfileOpen(false)` unconditionally even when the
dropdown is already closed.

```typescript
// BAD: listener runs on every click for the entire component lifetime
useEffect(() => {
  function handleClickOutside(e: MouseEvent) {
    if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
      setProfileOpen(false);
    }
  }
  document.addEventListener("mousedown", handleClickOutside);
  return () => document.removeEventListener("mousedown", handleClickOutside);
}, []); // ← empty array = attach once, never re-evaluate

// GOOD: listener is attached only while the dropdown is open
useEffect(() => {
  if (!profileOpen) return; // no-op and no listener when closed
  function handleClickOutside(e: MouseEvent) {
    if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
      setProfileOpen(false);
    }
  }
  document.addEventListener("mousedown", handleClickOutside);
  return () => document.removeEventListener("mousedown", handleClickOutside);
}, [profileOpen]); // re-runs when open state changes; cleanup fires on close
```

The `[profileOpen]` dep array causes React to run the cleanup function (which removes the listener)
every time `profileOpen` goes from `true` to `false`. When `profileOpen` is `false`, the effect
returns immediately without attaching anything.

---

## Prevention

### Code review checklist

- [ ] After every `await` in an event handler, check that all subsequent `setState` calls use the
  `prev =>` functional form when they reference array or object state.
- [ ] Any new dropdown or popover must use `!ref.current.contains(e.target as Node)` for
  click-outside detection. Flag any `closest()` calls in mousedown handlers.
- [ ] For any `useEffect` that attaches a `document` event listener, verify: (a) the dep array
  includes the open-state variable, and (b) the effect returns early when that state is `false`.

### Detection

| Bug | Lint catches? | Test catches? | Primary control |
|-----|--------------|--------------|----------------|
| Stale closure after await | No | With effort (async race test) | Code review |
| Inconsistent click-outside | No (grep possible) | Partially (behavior not pattern) | Code review |
| Unconditional listener | Partially (`exhaustive-deps` if open-state used inside) | Yes — spy on addEventListener | Code review + dep discipline |

`react-hooks/exhaustive-deps` (default Next.js ESLint config) catches Bug 3 only if `profileOpen`
is referenced inside the effect body. If the effect uses `[]` and references `profileOpen` outside,
the rule won't fire — manual review is required.

### Test for Bug 3 (worth adding)

```typescript
it("does not call addEventListener when the dropdown is closed", () => {
  const spy = vi.spyOn(document, "addEventListener");
  render(<TopNav />);
  // profileOpen starts false; no mousedown listener should have been attached
  expect(spy).not.toHaveBeenCalledWith("mousedown", expect.any(Function));
});
```

---

## Related Documentation

- `docs/solutions/ui-bugs/liquid-glass-dark-mode-invisible-white-tint-on-dark-backdrop.md`
  — Another UI bug that requires visual smoke-testing; similar "silent wrong behavior" category.
- No existing docs for React stale closures, click-outside patterns, or optimistic updates in this
  project — this is the first entry for these patterns.

---

## Status

Bugs identified in code review (2026-05-15). Not yet fixed. The correct implementations are shown
in the code examples above. Bug 1 (stale closure) and Bug 3 (unconditional listener) are the most
impactful to fix; Bug 2 (pattern inconsistency) is lower priority but should be addressed when the
next dropdown is added.
