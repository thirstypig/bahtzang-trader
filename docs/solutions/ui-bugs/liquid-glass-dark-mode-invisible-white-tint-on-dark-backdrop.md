---
id: DOC-050
type: solution
status: active
phase: null
owner: james
tags: [frontend]
links: []
updated: 2026-07-22
severity: medium
---

# Liquid-glass dark mode invisible — white tint over a dark backdrop disappears, not frosts

## Symptoms

- After deploying the Liquid Glass redesign (commit `f0e0382`), every glass surface in dark mode looked broken:
  - **Mega-menu dropdowns**: nearly transparent. Body radial-gradient (vivid pink/purple/cyan) bled through into the foreground.
  - **Cards** (`.bz-glass`): hard to distinguish from the page backdrop.
  - **Modals** (`.bz-glass-strong`): floating outlines without a coherent surface.
- **Light mode was correct**. Same CSS, same components, same backdrop-filter. The bug was theme-specific.
- User report (verbatim): *"the liquid glass is transparent and not clear"* and *"the background of the menu dropdown has issues."*
- A `.bz-glass-soft-alt` reference on the login page was also flagged — never existed as a class — but that was a separate, smaller bug (tracked in the redesign commit, not this one).

## Investigation Steps

1. **Reproduced the issue in headless Chrome** via Playwright:
   ```
   navigate http://localhost:3070/login
   evaluate "() => { localStorage.setItem('theme', 'dark'); document.documentElement.classList.add('dark'); }"
   take screenshot
   ```
   The dark-mode login card showed a faint outline barely visible against the body backdrop. Same surface in light mode rendered as a clear frosted card.

2. **Inspected the dark-mode tokens** in `globals.css`:
   ```css
   .dark {
     --glass-tint:     255 255 255;   /* WHITE */
     --glass-a1:       0.10;
     --glass-a2:       0.04;
     --glass-border:   255 255 255;
     --glass-border-a: 0.18;
     --glass-inset:    0.18;
     --glass-shadow:   0.30;
   }
   ```
   And the `.bz-glass` utility:
   ```css
   .bz-glass {
     background: linear-gradient(180deg,
       rgb(var(--glass-tint) / var(--glass-a1)),
       rgb(var(--glass-tint) / var(--glass-a2)));
     backdrop-filter: blur(20px) saturate(180%);
     ...
   }
   ```
   In dark mode this evaluates to `linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.04))` — 10% white at top, 4% at bottom.

3. **Compared to light-mode values**:
   ```css
   :root {
     --glass-tint:     255 255 255;   /* same WHITE */
     --glass-a1:       0.65;          /* 6.5x higher */
     --glass-a2:       0.40;          /* 10x higher */
   }
   ```
   Light mode also used white tint, but at 65%/40% alpha. The light-mode tint produced a visible frost over pastel backdrops; the dark-mode tint did not.

4. **Realized the design assumption was inverted.** The reasoning in the original tokens was: "dark mode should let the vivid backdrop show through more, so use lower alphas." That intuition is *opposite* to how alpha compositing actually works for *frosted* effects. Frost requires the surface to add *contrast* against what's behind. Over a bright backdrop, low-alpha white *does* add contrast (lightens the dark-blue-pixel regions of the photo to make the frost). Over a dark backdrop, low-alpha white *barely changes* the dark pixels — the surface contributes ~0.10 × white plus 0.90 × backdrop ≈ still mostly backdrop, with imperceptible whitening.

## Root Cause

**Apple's Liquid Glass design language was developed for bright photographic backdrops** (iOS wallpapers, Mac windows over colorful desktop pictures). White tint at low alpha is correct *there* because the luminance gap between the tint (pure white) and the backdrop (medium-bright photo) creates the frost effect.

**Dark mode in this app is the inverted case**: a dark vivid radial-gradient backdrop (#0e1424 base + radial gradients of #5b3fff, #ff5fa8, #15c0ff). White at 10% alpha applied over this looks essentially like the backdrop with a 10% white wash — invisible in most regions, slightly noticeable only where the backdrop is darkest.

The fix is **not** to crank up the alpha (tested: 0.30 / 0.20 still looked too transparent and washed out the colors behind), but to **invert the tint**. A NAVY tint (`rgb(18, 24, 48)`) at 55%/40% alpha produces an opaque-feeling dark frosted surface against the bright backdrop — the same way white-over-bright works in iOS, just with the luminances flipped.

## Solution

### 1. Switch dark-mode glass tint from white to navy

Change in `frontend/src/app/globals.css`:

```diff
   .dark {
-    --glass-tint:     255 255 255;
-    --glass-a1:       0.10;
-    --glass-a2:       0.04;
-    --glass-border:   255 255 255;
-    --glass-border-a: 0.18;
-    --glass-inset:    0.18;
-    --glass-shadow:   0.30;
+    /* Dark glass uses a NAVY tint (not white) so frosted surfaces read
+       as opaque chrome against the vivid radial backdrops. White edge
+       highlights are layered on top via border + inset shadow. */
+    --glass-tint:     18 24 48;
+    --glass-a1:       0.55;
+    --glass-a2:       0.40;
+    --glass-border:   255 255 255;
+    --glass-border-a: 0.16;
+    --glass-inset:    0.14;
+    --glass-shadow:   0.40;
   }
```

### 2. Keep the white edge highlight

Critical detail: the *border* and *inset shadow* stay white. They're what make the surface read as "glass" and not "matte navy panel." The border at `rgba(255 255 255 / 0.16)` is the white rim; the `inset 0 1px 0 rgba(255 255 255 / 0.14)` in `box-shadow` is the top-edge highlight. Both stay white in both themes.

### 3. Light mode unchanged

The light-mode tokens were already correct (white tint over pastel backdrop = proper frost). No changes needed.

### 4. Why .bz-glass-strong "just worked"

`.bz-glass-strong` multiplies the alphas by 1.2/1.4 to make the surface more opaque (used for the top nav and modals). In the broken state, that gave 12%/5.6% white — still mostly invisible. With the navy fix, it gives 66%/56% navy — fully opaque, looks like a heavier frosted slab. Same multiplier, very different visual outcome.

## Verification

Visual confirmation via Playwright after the fix landed:

```js
await page.goto('http://localhost:3070/login');
await page.evaluate("() => { localStorage.setItem('theme', 'dark'); document.documentElement.classList.add('dark'); }");
await page.screenshot({ path: 'login-dark.png' });
```

Before: card was a faint outline barely visible against the radial backdrop.
After: card reads as a proper navy frosted surface with a white rim, content clearly readable, vivid backdrop visible *around* the card but not bleeding *through* it.

## Prevention

### When designing glass surfaces, contrast the tint *against the backdrop*

The mental model: glass = backdrop + tint. The tint is what makes the glass look like a surface instead of a hole. The tint must be *visually distinct* from the backdrop, not just present.

- Bright backdrop (light pastels, photographs) → use a tint *lighter* than the backdrop (white at low alpha, ~10–30%)
- Dark backdrop (deep colors, near-black) → use a tint *darker* than the backdrop (near-black/navy at higher alpha, ~40–60%)
- Mid backdrop → either direction works, but pick the one that gives more luminance contrast

Don't try to "preserve the backdrop's vividness through low-alpha tinting" in dark mode. Vivid backdrops need *blocking* (or near-blocking) to make a coherent surface.

### Add a visual smoke-test step to the frontend deploy pipeline

Currently the frontend gate is `tsc + vitest + next lint`. None of these catch "this surface is invisible." Two practical mitigations:

1. **Manual visual check on Stage 0 of any redesign**: navigate the deployed site in both themes before declaring done. This is what caught the bug — a real Chrome render in dark mode.
2. **Visual regression snapshots** (e.g., Playwright `expect(page).toHaveScreenshot()`) for key pages in both themes. Heavy machinery; only worth the cost if redesigns happen often.

### Document the alpha/backdrop pattern in the theme system

The fix's commit message documented the rule, but it lives only in git history. Worth promoting to a comment block at the top of `globals.css` near the `.dark` token definitions, so the next person tweaking glass tokens reads "navy tint here is intentional — see commit `4086290` and `docs/solutions/ui-bugs/liquid-glass-dark-mode-invisible-white-tint-on-dark-backdrop.md`."

## Related

- `performance-issues/web-audit-accessibility-performance-ux-fixes.md` — Earlier comprehensive audit covering dark-mode contrast and Recharts theming. Loosely related; that doc handles *contrast* of text colors over surfaces, this one handles the surfaces themselves.

## When this might recur

- **Adding a third theme** (e.g., a sepia or high-contrast mode). Each theme's glass tokens must be designed against *that theme's* backdrop, not copy-pasted from another theme with adjusted alphas.
- **Switching from radial-gradient backdrops to photographic ones** in dark mode. A photo of a sunset over water has bright regions where white tint at low alpha *would* work. The current navy tint would over-block such a photo. Test before committing.
- **Bumping `backdrop-filter: blur` values significantly** without adjusting tint alpha. More blur means more averaging of backdrop pixels, which can shift the perceived backdrop luminance — sometimes pushing a previously-invisible tint into visibility (or vice versa).
- **Recharts (or any third-party rendering library) introducing colors** that don't pass through CSS variables. A chart's axis line at hex `#3f3f46` looks fine on a solid dark background but may compete visually with a navy glass surface; the chart-fix pattern in the redesign commit (passing CSS-var strings to Recharts inline-style props) is the workaround.
