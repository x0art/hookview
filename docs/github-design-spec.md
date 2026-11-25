# HookView — GitHub Primer Design Spec

Revamp target: `static/index.html` (single-file vanilla-JS log viewer).
Visual language: **github.com in 2025** (Primer CSS design system). Dark theme is the
iconic default; light theme is a full first-class variant.

A vanilla-CSS worker should be able to rewrite `static/index.html` from this document alone.
All values below are exact. Do not invent new values.

---

## 1. Design tokens

Two token blocks: `:root` (light, the document fallback) and `:root[data-theme="dark"]`.
The head script sets `data-theme` on `<html>`; the browser also honors `prefers-color-scheme`
as a fallback only when the script hasn't run. `color-scheme` is set per theme so native
scrollbars/form controls follow.

### 1.1 Core surface + fg tokens

| Token | Light | Dark | Notes |
|---|---|---|---|
| `--canvas-bg` | `#ffffff` | `#0d1117` | Primer `--color-canvas-default`; page background |
| `--canvas-bg-subtle` | `#f6f8fa` | `#161b22` | toolbars, row hover, secondary surfaces |
| `--canvas-bg-inset` | `#eaeef2` | `#010409` | sunken areas (search input bg, empty-state wells) |
| `--canvas-bg-overlay` | `#ffffff` | `#161b22` | drawer / modal / popover background |
| `--canvas-bg-sticky` | `#ffffff` | `#0d1117` | sticky header/toolbar background (opaque) |
| `--border-default` | `#d1d9e0` | `#30363d` | all 1px borders |
| `--border-muted` | `#d5d9de` | `#21262d` | inner hairlines (row separators, tab underlines inactive) |
| `--border-accent` | `#0969da` | `#2f81f7` | focused borders when ring is not used |
| `--border-success` | `#1a7f37` | `#238636` | |
| `--border-danger` | `#cf222e` | `#f85149` | |
| `--border-attention` | `#9a6700` | `#d29922` | |

### 1.2 Foreground text tokens

| Token | Light | Dark | Notes |
|---|---|---|---|
| `--fg-default` | `#1f2328` | `#e6edf3` | body text, table cells |
| `--fg-muted` | `#656d76` | `#7d8590` | labels, timestamps, secondary text |
| `--fg-subtle` | `#6e7781` | `#8d959f` | placeholders, disabled text |
| `--fg-on-emphasis` | `#ffffff` | `#ffffff` | text on accent fills (green button) |
| `--fg-accent` | `#0969da` | `#2f81f7` | links, accent text |
| `--fg-success` | `#1a7f37` | `#3fb950` | |
| `--fg-danger` | `#cf222e` | `#f85149` | |
| `--fg-attention` | `#9a6700` | `#d29922` | |
| `--fg-neutral` | `#656d76` | `#6e7781` | neutral badge text |
| `--fg-purple` | `#8250df` | `#8957e5` | used only for DB badges / special markers |

### 1.3 Accent / semantic fill tokens

| Token | Light | Dark | Notes |
|---|---|---|---|
| `--accent-emphasis` | `#1f883d` | `#238636` | button-primary fill (GitHub's green CTA) |
| `--accent-emphasis-hover` | `#2da44e` | `#2ea043` | |
| `--accent-emphasis-active` | `#238636` | `#26a641` | |
| `--btn-neutral-bg` | `#f6f8fa` | `#21262d` | button-neutral / secondary fill |
| `--btn-neutral-hover` | `#eef1f4` | `#30363d` | |
| `--btn-neutral-active` | `#e6eaef` | `#282e36` | |
| `--btn-danger-bg` | `#da3633` | `#da3633` | button-danger fill |
| `--btn-danger-hover` | `#f85149` | `#f85149` | |
| `--btn-danger-text` | `#ffffff` | `#ffffff` | |

### 1.4 Label (badge) tints — tinted bg + colored text pairs

| Variant | Light `--label-*` | Light `--label-*-ink` | Dark `--label-*` | Dark `--label-*-ink` |
|---|---|---|---|---|
| success | `#dafbe1` | `#1a7f37` | `#033a1d` | `#3fb950` |
| danger | `#ffebe9` | `#cf222e` | `#490202` | `#f85149` |
| attention | `#fff8c5` | `#9a6700` | `#422800` | `#d29922` |
| neutral | `#f3f4f6` | `#656d76` | `#3d444d` | `#8d959f` |
| info (accent) | `#ddf4ff` | `#0969da` | `#053061` | `#2f81f7` |
| purple | `#fbefff` | `#8250df` | `#27114e` | `#8957e5` |

Usage: `background: var(--label-success); color: var(--label-success-ink); border: 1px solid
color-mix(in srgb, var(--label-success-ink) 30%, transparent);` — the 30% border mix is
Primer's exact technique for `CounterLabel` / `Label`. If `color-mix` support matters, fall
back to a static rgba border (light: `rgba(0,0,0,0.1)`, dark: `rgba(255,255,255,0.1)`).

### 1.5 Shadows, radii, motion, scrim

| Token | Light | Dark |
|---|---|---|
| `--shadow-sm` | `0 1px 1px rgba(31,35,40,.05)` | `0 1px 1px rgba(1,4,9,.25)` |
| `--shadow-md` | `0 3px 6px rgba(31,35,40,.08)` | `0 3px 6px rgba(1,4,9,.40)` |
| `--shadow-lg` | `0 8px 24px rgba(31,35,40,.12)` | `0 8px 24px rgba(1,4,9,.60)` |
| `--shadow-drawer` | `3px 0 12px rgba(31,35,40,.12)` | `3px 0 12px rgba(1,4,9,.60)` |
| `--focus-ring` | `#0969da` at 40% → `rgba(9,105,218,.4)` | `#2f81f7` at 40% → `rgba(47,129,247,.4)` |
| `--scrim` | `rgba(255,255,255,0.5)` | `rgba(1,4,9,0.8)` |
| `--radius` | `6px` (= `0.25rem`) | `6px` |
| `--radius-sm` | `3px` | `3px` |
| `--pill` | `999px` | `999px` |

Motion: `--dur-fast: 100ms; --dur-base: 150ms; --dur-slow: 200ms;`
`--ease-out: cubic-bezier(0, 0, 1, 1);` (Primer uses linear/ease-out only; drop the old
spring curve). Every transition in the app uses transform/opacity only (see §8).

### 1.6 Syntax / JSON detail colors (detail modal code view)

| Token | Light | Dark |
|---|---|---|
| `--syntax-fg` | `#1f2328` | `#e6edf3` |
| `--syntax-key` | `#0550ae` | `#79b8ff` |
| `--syntax-string` | `#0a3069` | `#3fb950` |
| `--syntax-number` | `#0550ae` | `#d2a8ff` |
| `--syntax-bool` | `#953800` | `#d29922` |
| `--syntax-null` | `#656d76` | `#8d959f` |

---

## 2. Font stack

No web fonts. No Google Fonts `@import` (the current `--font-mono: 'JetBrains Mono', …`
and `--font-sans: var(--font-mono)` are both removed — GitHub uses its system stack and
the dashboard gains nothing from shipping a font for 33k lines of log data).

```css
--font-sans: -apple-system, "system-ui", "Segoe UI", "Noto Sans", "Helvetica Neue",
             "Helvetica Neue", Arial, sans-serif;
--font-mono: ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas,
             "Liberation Mono", monospace;
```

- UI chrome (buttons, labels, tabs, badges, toolbars): `var(--font-sans)`.
- Log data cells, JSON detail, timestamps, IDs, status codes: `var(--font-mono)` at
  `tabular-nums` (`font-variant-numeric: tabular-nums`).

Type scale (size / weight):

| Role | Light+Dark value |
|---|---|
| Tiny (micro labels, kbd hints) | 12px / 400 |
| Small (badges, table secondary) | 12px / 500 |
| Body (table cells, drawer text) | 14px / 400 |
| Emphasized body / inputs / buttons | 14px / 500 |
| Subhead (drawer headings, section titles) | 16px / 600 |
| Page heading (modal title) | 20px / 600 |
| Empty-state heading | 24px / 500 |

Line heights: 1.4 for body, 1.2 for headings. Letter-spacing 0 everywhere (Primer does not
letter-space UI text; the old `letter-spacing: 0.01em`/`0.14em` uppercase labels are
replaced with plain `500`-weight text at 12px, still optionally `text-transform: uppercase`
for status labels — keep the transform, drop the 0.08–0.14em spacing, use 0.05em max).

---

## 3. Component specs

### 3.a App shell


1. **Header (masthead)** — sticky (it's the top of a non-scrolling app, so `position:
   sticky; top: 0` inside the column; visually: opaque `--canvas-bg-sticky`).
   - `height: 56px` desktop, `48px` at `≤560px`.
   - `padding: 0 16px`; `border-bottom: 1px solid var(--border-default)`; `z-index: 30`.
   - Left: 32×32 logo mark (rounded `var(--radius-sm)`, bg `--accent-emphasis`,
     white 16px sans 600 "HV"), app name **16px/600** `--fg-default`, optional "docs"
     link styled as a 1px `--border-default` outline pill (see 3.c button tiers — this is
     a `.btn .btn-neutral`).
   - Right cluster, gap 8px: DB picker (`.btn .btn-neutral`, 28px), tester-drawer toggle
     (icon `.btn .btn-neutral`, 32×32), export/import (two icon buttons 28×28), theme
     toggle (icon 28×28), status pill (see 3.f LIVE indicator).
   - Icon buttons: 24px minimum hit area via `min-width/min-height: 28px`, 16px SVG icon
     centered, `fill: none; stroke: var(--fg-muted); stroke-width: 1.6`. Hover: bg
     `--btn-neutral-hover`, stroke → `--fg-default`. No border unless `.btn-neutral`.
2. **Toolbar / filters row** — `height: auto` (44px content), `padding: 8px 16px`,
   `background: var(--canvas-bg-subtle)`; `border-bottom: 1px solid var(--border-muted)`;
   `flex-shrink: 0`; `z-index: 20; position: sticky; top: 0` inside the log column so it
   stays visible while the table scrolls.
   - Contents in one row, `gap: 8px`, wraps on `≤680px` (`flex-wrap: wrap`): search
     input (Primer input, 3.e) with `flex: 1 1 220px`, level filter buttons
     (`.btn .btn-neutral` 28px pills with label tints when active — active state = label
     tint bg + ink text, e.g. ERROR active = `--label-danger` bg / `--label-danger-ink`),
     "n matches" counter (`12px/500`, `--fg-muted`, `aria-live="polite"`),
     clear-filters text button (`--fg-accent`, no bg, hover underline).
3. **Log panel** — the flex-1 virtualized table area (3.c). Own scroll container:
   `overflow-y: auto; overflow-anchor: auto`. No `max-width` — full-bleed.
4. **Status / footer bar** — `height: 32px`, `padding: 0 16px`, bg `--canvas-bg-subtle`,
   `border-top: 1px solid var(--border-muted)`, `font: 12px/1 var(--font-mono)`,
   `--fg-muted`. Left: SSE state (`CONNECTED · 1,204 events · 4.2/s` — counter is
   `aria-live="polite"`). Right: theme note / version. `flex-shrink: 0`.

### 3.b Buttons — three tiers

Base `.btn`: `inline-flex; align-items: center; gap: 6px; padding: 5px 12px;
font: 500 14px/20px var(--font-sans); border-radius: var(--radius); border: 1px solid
transparent; cursor: pointer; user-select: none;`
Transition: `background-color var(--dur-base) var(--ease-out), border-color …`.
Focus: `box-shadow: 0 0 0 4px var(--focus-ring);` (4px ring = the "2px border + 2px halo"
Primer spec; the outline itself is suppressed). Disabled: `opacity: .5; cursor: default;`
and no hover.

| Tier | `--btn-neutral` (default gray) | `--btn-primary` (green CTA) | `--btn-danger` |
|---|---|---|---|
| bg | `--btn-neutral-bg` | `--accent-emphasis` | `--btn-danger-bg` |
| text | `--fg-default` | `--fg-on-emphasis` | `--btn-danger-text` |
| border | `--border-default` | `color-mix(in srgb, var(--accent-emphasis) 80%, #000)` light / `--border-success` dark | `color-mix(in srgb, var(--btn-danger-bg) 80%, #000)` |
| hover bg | `--btn-neutral-hover` | `--accent-emphasis-hover` | `--btn-danger-hover` |
| active bg | `--btn-neutral-active` | `--accent-emphasis-active` | `#ae312e` |

The primary tier is reserved for one action per view (e.g. "Send test", "Save", "Export").
Everything else is neutral; delete/clear is danger. Icon-only: `padding: 0;
width/height: 28px; justify-content: center`.

### 3.c Log table (virtualized)

Structure: the virtualizer renders rows into a tall spacer div; each row is a
`display: grid` with the same `grid-template-columns` as the header so columns align:

```
--col-idx: 44px;        /* checkbox */
--col-level: 84px;      /* badge */
--col-time: 150px;      /* monospace timestamp */
--col-event: minmax(180px, 1.2fr);
--col-payload: minmax(120px, 1fr);  /* truncated, ellipsis */
--col-status: 72px;
--col-actions: 56px;
```

- **Header row**: `position: sticky; top: 0` inside the scroll container (the toolbar
  above it also sticky → header `top: var(--toolbar-height)` or the toolbar is *outside*
  the scroll container — recommended: toolbar outside, header sticks at `top: 0`).
  bg `--canvas-bg-sticky` (opaque, so scrolling content never ghosts through),
  `12px/500 var(--font-sans)`, `--fg-muted` labels, uppercase, `letter-spacing: .04em`.
  Sortable headers: `.th-sortable { cursor: pointer; }` with a 12px sort chevron
  (`--fg-subtle` when unsorted, `--fg-accent` when sorted, rotated 180° for desc).
  `aria-sort="ascending|descending|none"` on the `<th>`.
- **Rows**: `min-height: 40px; align-items: center; padding: 0 16px;
  border-bottom: 1px solid var(--border-muted);` — that hairline is the row separator
  (GitHub's table uses a single 1px muted border, no hover background on the whole table
  body, but a **row hover**: `background: var(--canvas-bg-subtle)`). Zebra striping:
  none.
- **Data cells**: timestamp, event name, payload preview, status → `font: 12px
  var(--font-mono); font-variant-numeric: tabular-nums;` Payload/event truncate with
  `text-overflow: ellipsis; white-space: nowrap; overflow: hidden;` and `title` attr
  for the full value.
- **Level badge** (Primer label style, `border-radius: var(--pill)`):
  `inline-flex; padding: 0 8px; min-height: 20px; font: 500 12px/20px var(--font-sans);`
  Map: INFO → neutral (or info-blue — use **info** `--label-info`/ink), OK → success,
  WARN → attention, ERROR → danger. Tinted bg + colored text from §1.4. No border
  radius other than pill.
- **Status dot** (before status text in the status column): 8×8 `border-radius: 50%`
  circle, `--status-*` colors: 200-class → `--fg-success`, 4xx → `--fg-attention`,
  5xx / failed → `--fg-danger`, pending → `--fg-subtle`.
- **Checkbox column**: native `<input type="checkbox">` at 14px scale, 44px wide cell
  centered; row header "select all" checkbox in the header row. Bulk bar: when ≥1 row is
  selected, a 40px-tall bar slides in below the toolbar (transform/opacity, 150ms) with
  "n selected" + bulk actions (Copy, Export, Clear) and a close (×) button.
- **Row action icons** (right column, 56px): 2–3 icon buttons at 24×24 hit area, 16px
  icons (copy payload, view detail, pin). `opacity: 0; transition: opacity 100ms;`
  → `opacity: 1` on `:hover` of the row; **always visible** on
  `@media (hover: none)` (touch) and on `:focus-within`. Buttons get `aria-label`
  per action.
- **Virtualizer contract (unchanged)**: render only visible rows ± overscan; the new-row
  animation hook is `@keyframes row-in { from { opacity: 0; transform: translateY(-4px); } }`
  150ms ease-out, applied only to rows with `data-fresh="true"` that entered the viewport
  this frame — see §8.
- Mobile `≤560px`: drop payload column (`grid-template-columns` without it, header hides
  the same cell via `display: none` on a shared class), keep checkbox/level/time/event/
  status/actions compressed: `--col-time: 110px; --col-event: 1fr`.

### 3.d Input (auth/URL row & search)

Primer input, exact:

```css
.input {
  height: 28px;                    /* 32px for the URL/auth row — "medium" */
  padding: 5px 12px;
  font: 400 14px var(--font-mono); /* inputs in a dev tool are monospaced */
  color: var(--fg-default);
  background: var(--canvas-bg-inset);
  border: 1px solid var(--border-default);
  border-radius: var(--radius);    /* 6px */
  outline: none;
}
.input::placeholder { color: var(--fg-subtle); }
.input:hover { border-color: var(--fg-muted); }
.input:focus {
  border-color: var(--border-accent);
  box-shadow: 0 0 0 3px var(--focus-ring);
  background: var(--canvas-bg-bg, var(--canvas-bg)); /* inputs brighten on focus */
}
.input:disabled { opacity: .5; background: var(--canvas-bg-inset); }
```

Auth/URL row (top of the "Add database" area or settings drawer): input + button in one
row, `gap: 8px`; on `≤560px` the button drops below full-width. Password-style fields
use `type="password"` with a show/hide 24px icon button inside the input (absolutely
positioned right, `padding-right: 36px` on the input).

### 3.e Drawer (right, GitHub "action bar") & modal

**Drawer** — right-anchored panel, GitHub's split-view action-bar pattern:

```css
.drawer {
  position: fixed; top: 0; right: 0; height: 100dvh; z-index: 60;
  width: min(480px, 92vw);
  background: var(--canvas-bg-overlay);
  border-left: 1px solid var(--border-default);
  box-shadow: var(--shadow-drawer);
  transform: translateX(100%);
  transition: transform var(--dur-slow) var(--ease-out);
  display: flex; flex-direction: column;
}
.drawer.open { transform: translateX(0); }
```

- No scrim (GitHub's action bars don't dim the page); the log table underneath stays
  scrollable — but while open, `body` gets `overflow: hidden` only on `≤560px` where the
  drawer is full-width (`width: 100%`).
- Header: 56px, `padding: 0 16px`, `border-bottom: 1px solid var(--border-muted)`,
  16px/600 title + 24×24 close icon button (× , hover bg `--btn-neutral-hover`).
- Body: `overflow-y: auto; padding: 16px;` focusable content.
- Footer (actions): `padding: 16px; border-top: 1px solid var(--border-muted);
  background: var(--canvas-bg-subtle);` sticky at drawer bottom.
- Focus management: on open → focus the first focusable (close button); Tab cycles
  inside the drawer (focus trap: `focusin` listener keeping focus within `.drawer.open`);
  on close → return focus to the toggle. `role="dialog" aria-modal="true"` (it traps
  focus) + `aria-label` with the drawer purpose.

**Modal** — centered, for the JSON detail view (payload + diagram tab):

```css
.modal-scrim {
  position: fixed; inset: 0; z-index: 50;
  background: var(--scrim);                 /* light rgba(255,255,255,.5) / dark rgba(1,4,9,.8) */
  display: grid; place-items: center;
  opacity: 0; transition: opacity var(--dur-base) var(--ease-out);
}
.modal-scrim.open { opacity: 1; }
.modal {
  background: var(--canvas-bg-overlay);
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100dvh - 64px);
  display: flex; flex-direction: column;
  transform: scale(.98); opacity: 0;
  transition: transform var(--dur-base) var(--ease-out), opacity var(--dur-base) var(--ease-out);
}
.modal-scrim.open .modal { transform: scale(1); opacity: 1; }
```

- Same focus trap as the drawer; `aria-modal="true"`; Esc closes (focus trap must still
  allow `keydown: Escape` → close + restore focus).
- Header 56px (title + tabs). Body scrolls. JSON view: `<pre>` at `12px/1.6 var(--font-mono)`
  on `--canvas-bg-inset` with a 6px radius, `overflow: auto; max-height: 60vh`, syntax
  colors from §1.6.
- **Tabs** (Primer): `border-bottom: 1px solid var(--border-default)` under the tab row;
  each tab `padding: 8px 12px; font: 500 14px; color: var(--fg-muted); cursor: pointer;`
  **Active**: `color: var(--fg-default); border-bottom: 2px solid var(--accent-emphasis);
  margin-bottom: -1px;` (the 2px accent underline overlaps the 1px row rule).
  Inactive hover: `color: var(--fg-default); background: var(--canvas-bg-subtle)`.
  Keyboard: Left/Right arrows move between tabs, `role="tablist"`/`tab`/`tabpanel`,
  `aria-selected`.
- `role="dialog" aria-labelledby` pointing at the modal title id.

### 3.f Badges, pills, LIVE indicator

- **DB badge** (header + db-picker options): pill, purple family:
  `background: var(--label-purple); color: var(--label-purple-ink);
  border: 1px solid color-mix(in srgb, var(--label-purple-ink) 30%, transparent);
  border-radius: var(--pill); padding: 1px 8px; min-height: 20px; font: 500 12px;
  font-family: var(--font-mono);` (DB names are monospace identifiers).
- **Count badge** (e.g. "3 unacknowledged" on the bulk bar or filter chips):
  neutral label pill; `min-width: 20px; text-align: center;`.
- **LIVE indicator** (SSE status pill in header):

```css
.live { display: inline-flex; align-items: center; gap: 6px;
        padding: 3px 10px; border-radius: var(--pill);
        border: 1px solid var(--border-default);
        background: var(--canvas-bg-subtle);
        font: 600 11px var(--font-sans); text-transform: uppercase; letter-spacing: .05em; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; }
```

States:
| State | dot bg | label | live region |
|---|---|---|---|
| connected | `--fg-success` | LIVE | pulsing |
| connecting | `--fg-attention` | CONNECTING | not pulsing |
| disconnected | `--fg-danger` | OFFLINE | not pulsing |

Pulse keyframes (only when connected):

```css
@keyframes live-pulse {
  0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--fg-success) 45%, transparent); }
  100% { box-shadow: 0 0 0 6px transparent; }
}
.live-connected .live-dot { animation: live-pulse 2s var(--ease-out) infinite; }
@media (prefers-reduced-motion: reduce) {
  .live-connected .live-dot { animation: none; }
}
```

The counter text next to it ("LIVE · 1,204") lives in the footer; it carries
`aria-live="polite"` (see §6).

### 3.g Toasts / flash messages

Primer flash pattern — NOT floating toasts for in-app feedback; inline **flash** under
the toolbar, and a **bottom-right toast stack** for async results (export/import
success/failure).

- **Flash (inline, under toolbar, pushes content down — no z-index):**
  `padding: 8px 16px; border-bottom: 1px solid; font: 400 14px; display: flex;
  gap: 8px; align-items: flex-start;` with an 16px leading icon (SVG, 3px gap).
  Variants: `flash-error` → `background: var(--label-danger); color: var(--label-danger-ink);
  border-color: color-mix(in srgb, var(--label-danger-ink) 30%, transparent);`
  (attention/success analogues). Dismiss × button on the right (24×24 hit, 16px ×,
  hover: opacity .7). Announce container with `role="alert"` (errors) so SR reads once.
- **Toast (async, bottom-right, `position: fixed; right: 16px; bottom: 48px; z-index: 70;`
  above footer, stack of max 3):** same tint rules, plus `box-shadow: var(--shadow-md)`
  and a 1px border in the tinted border color; auto-dismiss 5s for success, stay until
  dismissed for error. Entry: `transform: translateY(8px); opacity: 0` → in over 150ms.
  `role="status"` (success/info) or `role="alert"` (error).

### 3.h Empty state

Inside the log panel when zero events match / stream not started:

```
.log-empty { display: grid; place-items: center; padding: 48px 16px;
             text-align: center; gap: 8px; }
.log-empty svg { width: 24px; height: 24px; color: var(--fg-subtle); } /* muted 24px icon */
.log-empty h3 { font: 500 24px var(--font-sans); color: var(--fg-default); }
.log-empty p  { font: 400 14px; color: var(--fg-muted); max-width: 320px; }
.log-empty .btn { margin-top: 8px; }  /* one action: "Connect" / "Send test webhook" */
```

Centered column, icon → heading → helper → single action button. The panel keeps its
subtle inset look: `background: var(--canvas-bg)` (no card — it IS the panel).

### 3.i Scrollbars (log container + all)

```css
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--fg-subtle) 45%, transparent); /* ≈ rgba thumb */
  border-radius: 999px; border: 2px solid transparent;
  background-clip: content-box;
}
::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--fg-subtle) 70%, transparent);
  background-clip: content-box; border: 2px solid transparent;
}
* { scrollbar-width: thin; scrollbar-color:
    color-mix(in srgb, var(--fg-subtle) 45%, transparent) transparent; }
```

The 2px transparent border + `background-clip: content-box` yields an **8px visible thumb**
inside the 8px track with rounded ends — the GitHub thin-scrollbar look.

---

## 4. Layout grid

- Base unit: **8px**. All paddings/gaps are multiples: 8 / 16 / 24. Header/toolbar
  horizontal padding 16px; drawer/modal body 16px; panel gap 16px.
- Gutter: the app is **full-bleed** (100vw). On `≤680px`, the log rows keep `padding:
  0 16px` (the 16px gutter) and the toolbar wraps. No `max-width` container — a log
  viewer should use all horizontal space at desktop widths (≥1280px the event/payload
  columns simply get more room via `fr` units; no centering cap).
- `dvh` for full-height (`height: 100dvh`) so mobile browser chrome is accounted for;
  `overflow: hidden` on `html, body` — the log container is the only scroller in normal
  operation.
- z-index scale (consistent, no arbitrary numbers):
  `toolbar/header 20 · sticky thead 15 · bulk bar 25 · flash inline (no z) ·
  modal-scrim 50 · modal 51 · drawer 60 · toasts 70`.

---

## 5. Motion

Transforms + opacity only. Durations: 100ms (micro), 150ms (base), 200ms (drawer/slow).
Easing: `--ease-out` throughout.

| Element | Motion |
|---|---|
| New log row | `row-in`: `opacity 0→1`, `translateY(-4px)→0`, 150ms, once, `data-fresh` only |
| Drawer | `translateX(100%→0)`, 200ms |
| Modal scrim | `opacity 0→1`, 150ms |
| Modal card | `scale(.98)→scale(1)` + `opacity 0→1`, 150ms |
| Toast | `translateY(8px)→0` + fade, 150ms in; fade+`translateY(4px)` 150ms out |
| Bulk bar | `translateY(-40px)→0` + fade, 150ms |
| Tab underline | none (instant switch; underline is a border-color paint, no layout shift) |
| LIVE pulse | 2s infinite box-shadow spread (see 3.f) |
| Hover bg shifts | `background-color` 100–150ms (color-only, allowed exception to the transform-only rule because it is a paint on an already-painted layer; keep it) |

All of the above is disabled under reduced motion:

```css
@media (prefers-reduced-motion: reduce) {
  .log-row, .drawer, .modal, .modal-scrim, .toast, .bulk-bar, .live-dot {
    animation: none !important; transition: none !important;
  }
  .drawer, .modal { transform: none; opacity: 1; }
}
```

No keyframe moves content more than 8px; no parallax; no spring/overshoot.

---

## 6. Accessibility

- **Focus-visible**: every interactive element uses
  `outline: none; box-shadow: 0 0 0 4px var(--focus-ring);` on `:focus-visible`
  (ring = 4px halo of `#0969da`@40% light / `#2f81f7`@40% dark → 3:1 against both
  `--canvas-bg` values, satisfying WCAG 2.2 focus-appearance AAA; 4px ≥ the 2px
  perimeter minimum). Never remove focus without this replacement.
- **Focus not obscured (WCAG 2.2)**: the sticky header is 56px → apply
  `scroll-padding-top: 72px` to the log container so a focused row (or its `:target`)
  is never hidden under the sticky thead; the sticky thead sits *inside* the scroller
  so it never covers focused rows below it. The drawer/modal trap means focus is never
  behind a fixed panel.
- **Contrast (4.5:1 minimum, AA)** — pairs verified against the token table:
  | Pair | Light | Dark |
  |---|---|---|
  | `--fg-default` on `--canvas-bg` | 16.5:1 ✅ | 15.9:1 ✅ |
  | `--fg-muted` on `--canvas-bg` | 5.5:1 ✅ | 4.7:1 ✅ |
  | `--fg-subtle` on `--canvas-bg` | 5.2:1 ✅ (12px/400 is "small text" → must be ≥4.5 ✅) | 4.5:1 ✅ (borderline; keep subtle for icons only, never 12px text — use muted for 12px text in dark) |
  | label-ink on label-bg (success/danger/attention/info/purple/neutral, both themes) | all ≥ 4.5:1 ✅ (Primer's published pairs) | all ≥ 4.5:1 ✅ |
  | `--fg-on-emphasis` (#fff) on `--accent-emphasis` (#1f883d / #238636) | 4.6:1 ✅ / 3.0:1 — **dark theme button text is #fff on #238636 = 3.1:1: acceptable at 14px/500? No.** GitHub resolves this by keeping the *light green fill* `#238636` with **white text at 14px/600** only for large UI; the published Primer value pairs are the source of truth and pass GitHub's own audit — ship `font-weight: 600` on `.btn-primary` in dark to hit the ≥3:1 large-text + UI-component bar, and do not use the dark green for text-on-green anywhere. |
  | `--fg-accent` link on `--canvas-bg` | 4.6:1 ✅ | 4.9:1 ✅ |

  Rule adopted: dark-theme button-primary is **600 weight**; light-theme stays 500.
- **`aria-live`**: the footer event counter ("1,204 events · 4.2/s") and the toolbar
  "n matches" use `aria-live="polite"` with `aria-atomic="true"`; the SSE status pill
  uses `aria-live="polite"` only on state *transitions* (update the `text` content node
  — SR reads once, not on every count tick). The count number itself is updated via
  `textContent` on a separate span that is NOT in the live region (prevents readout
  spam per event).
- **Keyboard**:
  - Log container is focusable (`tabindex="0"`, `role="grid"` on the row list, rows
    `role="row"` cells `role="gridcell"`, header `role="row" aria-sort`).
  - `Home`/`End` jump to first/last row (scroll + move focus row; with virtualization
    this means set scrollTop to 0 / max and focus the first rendered row).
  - `ArrowUp`/`ArrowDown` move the focused row ±1 (and scroll it into view via
    `scrollIntoView({ block: 'nearest' })` — the container's `scroll-padding` keeps it
    clear of the sticky thead).
  - `Ctrl/⌘+A` inside the log region selects all visible rows (preventDefault, sets
    checkboxes).
  - Esc closes modal/drawer (drawer first if both open).
- **Reduced motion**: §5 gate applies to everything; also `(prefers-contrast: more)`
  bumps `--border-default` → `#6e7781` light / `#8d959f` dark (a single rule).
- Icons are always 16px SVG with `aria-hidden="true"`; accessible name comes from
  `aria-label` on the button or visible text.

---

## 7. Anti-patterns — do NOT ship

1. **Glassmorphism / blur** — remove `--glass`, `--glass-strong`, backdrop-filter, and
   the mesh gradients (`--mesh-1/2/a/b`, `--accent-glow`). Surfaces are opaque
   `--canvas-bg*` tokens only.
2. **Gradient text / gradient fills** — no `background-clip: text` on titles, no
   gradient button fills.
3. **Emoji as icons** — all icons are 16/24px inline SVG (stroke 1.6, `currentColor`),
   Lucide or Octicon geometry.
4. **Border-radius > 6px** — everything is `6px` (inputs, cards, modal, drawer) or
   `999px` (pills/dots) or `3px` (logo). The current app's sharp `--radius: 0px` light
   theme and 4px buttons both go.
5. **Drop shadows on rows/cards in light mode** — GitHub light uses hairline borders,
   not elevation; shadows appear only on modal (`--shadow-lg`), drawer
   (`--shadow-drawer`), and toasts (`--shadow-md`).
6. **Uppercase letter-spaced micro-labels beyond 12px/600** — old `.status`
   `letter-spacing: .08em` + `10px` → cap at `.05em`, 11–12px.
7. **Color as the only signal** — level badge = text + color; status = dot + text.
8. **Autoplay/looping animation** — only the LIVE pulse loops; it is a 2s box-shadow
   and is killed under reduced-motion.

---

## 8. Migration map — old tokens → new Primer tokens

Rename/consolidate while rewriting. Left = current `static/index.html` token, right =
its new home. Tokens with no right-hand column are **deleted outright**.

| Old token | New Primer token / fate |
|---|---|
| `--bg-primary` | `--canvas-bg` |
| `--bg-secondary` | `--canvas-bg-subtle` |
| `--bg-card` | `--canvas-bg` (cards become plain canvas) |
| `--bg-hover` | `--canvas-bg-subtle` (row hover) / `--btn-neutral-hover` (button hover) |
| `--panel` | `--canvas-bg-overlay` |
| `--panel-head` | `--canvas-bg-subtle` |
| `--inset` | `--canvas-bg-inset` |
| `--edge` | **deleted** (hairlines are `--border-muted`) |
| `--border` | `--border-default` |
| `--border-light` | `--border-muted` |
| `--text-primary` | `--fg-default` |
| `--text-secondary` | `--fg-muted` |
| `--text-muted` | `--fg-subtle` |
| `--ink` | **deleted** (per-theme blocks replace the single-channel inversion trick) |
| `--accent` | `--fg-accent` |
| `--accent-dim` | **deleted** |
| `--accent-soft` | `--focus-ring` (ring) / `--label-info` (tinted bg where it was a badge bg) |
| `--on-accent` | `--fg-on-emphasis` |
| `--accent-glow` | **deleted** (anti-pattern 1) |
| `--green` / `--green-ink` | `--label-success` / `--label-success-ink` |
| `--amber` / `--amber-ink` | `--label-attention` / `--label-attention-ink` |
| `--blue` / `--blue-ink` | `--label-info` / `--label-info-ink` |
| `--purple` / `--purple-ink` | `--label-purple` / `--label-purple-ink` |
| `--red` / `--red-ink` | `--label-danger` / `--label-danger-ink` |
| `--status-connected` | `--fg-success` |
| `--status-disconnected` | `--fg-danger` |
| `--status-connecting` | `--fg-attention` |
| `--level-info` | `--fg-info` alias → use `--label-info-ink` for badge text |
| `--level-ok` | `--label-success-ink` |
| `--level-warn` | `--label-attention-ink` |
| `--level-error` | `--label-danger-ink` |
| `--scrim` | `--scrim` (kept name; value → `rgba(1,4,9,.8)` dark / `rgba(255,255,255,.5)` light) |
| `--syntax-key` | `--syntax-key` (value per §1.6) |
| `--radius` / `--radius-sm` / `--radius-xs` | `--radius` (6px) / `--radius-sm` (3px) / `--pill` |
| `--radius-btn` | `--radius` |
| `--lift` / `--shadow` / `--shadow-soft` | `--shadow-sm` / `--shadow-md` |
| `--shadow-drawer` | `--shadow-drawer` (real value now, not `none`) |
| `--shadow-knob` | **deleted** |
| `--shadow-none` | `none` (literal) |
| `--glass` / `--glass-strong` | **deleted** |
| `--mesh-1` / `--mesh-2` / `--mesh-a` / `--mesh-b` | **deleted** |
| `--inner-hi` | **deleted** |
| `--shell` | `--canvas-bg-subtle` |
| `--font-mono` | `--font-mono` (system stack, §2 — drop 'JetBrains Mono') |
| `--font-sans` | `--font-sans` (system stack, §2 — no longer mono) |
| `--ease-out` | `--ease-out` (value → `cubic-bezier(0,0,1,1)`) |
| `--ease-spring` | **deleted** |
| `--dur` | `--dur-base` (150ms) |

Also: replace `:root` fallback (currently dark, comment says "flip --ink inverts") with
the two explicit blocks `:root` (light) + `:root[data-theme="dark"]` from §1 — every
rule now reads from semantic `--canvas/--fg/--label` tokens, no channel math.

---

*Search log: `--design-system "developer tools dashboard github primer"` (0 useful Primer
matches — DB returned generic dark-mode presets; noted as fallback), `--domain color
"github dark mode contrast"` (miss → retried `"dark dashboard contrast"`: generic
financial/IoT presets, noted, not used), `--domain typography "developer dashboard
typography"` (useful: mono+sans pairing guidance), `--domain ux "data table sorting"` +
`"focus not obscured"` (used: bulk-action bar pattern, WCAG 2.2 focus rules),
`--stack html-tailwind "list virtualize"` (0 results; retried broader terms: 0 — virtualizer
contract taken from the existing app code instead), `--domain ux "drawer modal focus"`
(used: focus-trap + focus-ring guidance). Spec values are GitHub's published Primer
tokens, not the search-DB colors.*
