# Design Brief — HookView Stream Log Viewer

Scope: the live log table in `static/index.html` (the SSE-fed stream view). Report only; no code changes.
Grounded in the `ui-ux-pro-max` skill (searches below) + the app's existing dark theme tokens (`static/index.html` `:root`).
Contrast ratios computed with WCAG relative-luminance against the app's real surfaces.

---

## Sources (which search returned which guidance)

| # | Query / domain | Result used |
|---|----------------|-------------|
| S1 | `--design-system` "log stream dashboard terminal dark" (motion 2, density 8) | Style **Dark Mode (OLED)**; palette **Terminal dark + success green** (Coding Bootcamp product family: bg `#020617`-class OLED, `#0F172A` primary, `#22C55E`/`#16A34A` green, `#EF4444`/`#DC2626` destructive); typography **Fira Code / Fira Sans** "Dashboard Data" pairing; motion snippet Scroll Reveal Subtle (300–400 ms, `power1.out`, reduced-motion skip); pre-delivery checklist (no emoji icons, focus visible, hover 150–300 ms, 4.5:1). NOTE: the design-system's PATTERN output ("Hero + Testimonials + CTA") is marketing-pattern mismatch for a dashboard — **discarded**; only style/color/typography/motion/effect sections apply. The app's shipped palette is already in the same family (OLED `#050608` bg, `#22d3ee` cyan accent), so I keep shipped tokens and add level colors on top. |
| S2 | ux "auto scroll sticky bottom" / "user scrolled up pause auto-scroll" | **Auto-Rotating Content Controls** (Auto-advance without a stop control = High): give play/pause, stop on user intent. No dedicated "sticky bottom" rule exists in DB — the sticky-bottom spec below is a synthesis of that rule + the existing `shouldAutoScroll()` 100px threshold in code. |
| S3 | ux "streaming feed readability" | Line height 1.5–1.75 body (Medium) — app already at 1.55; Streaming = render incrementally, never block with spinner. |
| S4 | ux "touch min target 44px" | Web targets: WCAG Target Size (24 CSS px min, 44 preferred on touch); **8 px min gap** between adjacent targets (Medium); enlarge on mobile (High). App's row actions are 27×27 px with 1 px gap → below web min. |
| S5 | ux "live badge count screen reader" | **Contextual Live Badge Updates** (High): one atomic `role="status"` message, never a bare `aria-live` number, never multiple competing live regions. |
| S6 | ux "append layout shift" | **Content Jumping** (High): reserve space / stable containers; inserting badges must not push the toolbar. |
| S7 | ux "keyboard focus home end" | **Focus States** (High): visible ring on every control; **Focus Not Obscured (AA)**: sticky UI must not cover focus — offset with `scroll-padding`. |
| S8 | ux "aria live log region" | ARIA Labels (High, icon buttons need `aria-label`) + S5's rule. |
| S9 | ux "scroll keyboard" → **Motion Sensitivity** (High): honor `prefers-reduced-motion`, present final readable state, no scroll-jacking. |
| S10 | typography "monospace code log" | **Terminal CLI Monospace** (JetBrains Mono; sizes 12/14/16 only; weight 400; 1.2× for data density) + **Dashboard Data** (Fira Code/Fira Sans). App ships `--font-mono` — align to a 12/13/16 step, mono for data cells. |
| S11 | color "dark terminal contrast" / "warning amber" | **RPA/Automation Dashboard** note: "running green + failed red + queued amber" — the exact semantics we need for log levels. Amber `#F59E0B`/`#FBBF24` family. |
| S12 | gsap "enter animation reduced motion" | Skeleton/loader loop rules (kill on unmount, pause offscreen/hidden, reduced-motion → static final state). Applied to entry animation + LIVE pulse. |
| S13 | gsap "enter exit faster" | Subtle Scroll-Reveal tier: enter 300–400 ms `power1.out`, y 8–16 px; skip under reduced motion. Exit (cap/drop) should be instant or shorter than enter. |
| S14 | react stack "list virtualize" | **Virtualize long lists** (High): window >100 items — react-window/react-virtual; **stable keys** (High): `item.id`, never index. (App is a Vite+TS React island `frontend/` embedded in the vanilla page; if the stream table moves to React, this applies directly. For the vanilla table, the DOM-cap equivalent is specified in §C.) |
| S15 | ux "virtualize lists" → **0 results** (explicit fallback noted in §C); stack `html-tailwind` "list virtualize" → **0 results**; react "throttle" / ux "debounce throttle" → **0 results** (throttle/rAF guidance in §C is from the skill's quick-reference §3 `debounce-throttle` row + general web best practice, labeled as such, not DB matches). |

---

## A. Design system (dark mode)

Keep the shipped OLED family; it already matches S1's Dark Mode (OLED) style + Terminal-dark palette and passed every contrast check.

### Surfaces & text (existing, verified)
| Token | Hex | Ratio on `--bg-card #11141b` | Status |
|---|---|---|---|
| `--bg-primary` | `#050608` | — | OLED base (matches S1 bg `#020617` family) |
| `--bg-card` | `#11141b` | — | table panel |
| `--text-primary` | `#e6ebf2` | 15.4:1 | AA/AAA ✓ |
| `--text-secondary` | `#a7b0bd` | 8.4:1 | AA ✓ |
| `--text-muted` | `#8a94a3` | 6.0:1 | AA ✓ (IDs, timestamps) |
| `--accent` | `#22d3ee` (on-accent `#04121a`) | 10.5:1 | focus ring, links, LIVE dot |
| `--border` / `--border-light` | ink @ 0.08 / 0.16 | hairlines, not text | keep |

### Log-level semantic colors (new) — S11 "running green + failed red + queued amber"
Apply as **text/glyph tint on the level badge**, not full-row floods (avoids low-contrast + eye strain). Badge: level glyph + word, 12 px uppercase, on `--bg-hover` chip.

| Level | Hex | On `#11141b` | On badge chip `#1a1f2b` | Notes |
|---|---|---|---|---|
| default/info | `#60a5fa` (blue) | 7.25:1 | ~8.0:1 | AA ✓ (S11 "queued" blue family) |
| success/ok | `#34d399` (green) | 9.6:1 | ~10.4:1 | AA ✓; also `--status-connected` |
| warn | `#fbbf24` (amber) | 11.0:1 | ~11.9:1 | AA ✓ |
| error | `#f87171` (red) | 6.7:1 | ~7.4:1 | AA ✓; also `--status-disconnected` |

All ≥ 4.5:1 (S1 requires `contrast-text-4.5`). Do **not** rely on color alone: pair every level with a glyph/word (S-chart rule: "relying on color alone" is the anti-pattern; also covers low-vision + print). Never use pure `#ef4444`/`#dc2626` *as text* (4.8:1 white-on-red is for the badge fill only).

### Typography (S10 + S3)
- **Body/data (log rows): `--font-mono`, 13 px, line-height 1.5** (1.5–1.75 band from S3). Keep 13 px — S10's "12/14/16 only" is a strict-terminal rule; 13 is the app's current value and stays ≥ 12 px floor, so keep but cap the step at 12 / 13 / 16 (no 10–11 px sub-text in rows). The `th` at 10 px uppercase is acceptable as a **non-data label** but move to 11 px for AA at that size.
- **Sans for chrome/labels**: keep the UI label font (Fira Sans-class / system sans) for buttons, badges' words, empty state; mono reserved for `#`, timestamp, IP, payload, file (S10 "Code for data, Sans for labels").
- Weight 400 for data (S10: bold ruins mono); 500/600 only for badges/headers.

### Spacing (density 8 dial from S1)
Dashboard dense scale: **4 / 8 / 12 / 16 px** rows & gutters. Row vertical padding 8–10 px (app is 11 px — fine, but cap at 10 px to raise visible rows/viewport). Adjacent interactive targets ≥ 8 px gap (S4).

---

## B. Sticky-bottom auto-scroll spec

Replace the current `scrollTrack` + `scrollToBottom` link with one model. State machine on `#logContainer`:

| State | Condition | Behavior on new entry |
|---|---|---|
| **STICKY** | auto-follow ON **and** user at bottom (`scrollHeight - scrollTop - clientHeight <= 60` — code uses 100; tighten to 60 so "near bottom" is genuinely near) | Append + keep pinned to bottom. Newest entry visible on arrival. |
| **PAUSED** | user scrolled up > 60 px (auto-follow still ON) | New entries append but **do not** move the viewport (no yank). Show the jump pill. |
| **OFF** | user toggled auto-follow OFF | Same as PAUSED, but pill reads "N new · tap to resume". |

Interaction states & affordances (all S2 "Auto-Rotating Content Controls": must have a stop control + must stop on user intent):

1. **Jump-to-latest pill** (floating, bottom-center of the *panel*, `position:absolute` inside `.log-shell` so the page never scrolls — S6/S14 fixed-overlap rule):
   - Shows only in PAUSED/OFF when `pendingCount > 0`.
   - Copy: **`↓ {N} new`** when auto-follow is ON (click → resume + smooth scroll to bottom); **`▶ Resume · {N} new`** when OFF.
   - Min 44 px tall, `--accent` fill / `--on-accent` text (10.5:1), `border-radius` pill, shadow `--shadow-soft`. Enter: fade+`y:8` 150 ms (S13, subtle tier). Exit: instant (exit faster than enter).
   - Count source = number of entries appended while not STICKY. Resets to 0 on jump.
   - It is the **only** live counter. Do not also run `role="status"` per-entry (S5: "never make every badge a competing live region").
2. **Toggle** (`role="switch"`, keep `aria-checked`): label **"Auto-scroll"**, 44 px target, 8 px from neighbors. On turn-ON while PAUSED → immediately jump to bottom once (current `scrollToBottomOfList()` behavior — keep).
3. **Resume-on-reach**: if user manually scrolls back within 60 px of bottom, auto-clear the pill and re-enter STICKY (auto-follow ON only) — removes the "fights the user" feel.
4. **Reduced motion** (S9): `prefers-reduced-motion: reduce` → the jump and entry animations become **instant** (no smooth scroll, no `slideIn`), but auto-follow + pill still work. Never scroll-jack.
5. New entry animation (S13): only for the single newest row, `slideIn` 200–300 ms `power1.out`, **opacity 0→1 + y 8→0 only** (no width/height, S2 anti-pattern "animating width/height"). Skip entirely under reduced motion. Do not animate on bulk history load (S12: elaborate motion for sub-threshold/async content flashes).

Missed-entry count math: keep a monotonic `pendingCount` incremented in `addLogEntry()` only when not STICKY; cleared on jump / on reach-bottom.

---

## C. Layout spec

### Isolated scroll container (core fix — page never scrolls)
- `.log-shell` is `flex:1; min-height:0` inside `.main-area` (app already has this — correct). Enforce **`overflow:hidden` on `.app`** and let **only `#logContainer` scroll** (`overflow-y:auto`). Remove the `scrollToBottom` footer link from the *page* footer; the pill (B) replaces it inside the panel. Page/`body` gets `overflow:hidden` so ambient `.bg-mesh/.bg-grain` stay fixed and the whole document can never scroll. This kills "the whole page scrolls instead of the panel."
- **Sticky thead inside the panel** (existing `position:sticky; top:0` on `.log-table thead`) — keep; it's the "reserved header/toolbar" and survives panel scroll. Toolbar (search/toggles/Export) stays a reserved row above the panel with fixed height; no reflow when content changes (S6).

### Append-only, no layout shift (S6 "Content Jumping", High)
- Newest entries are `prepend`ed to `#logBody` (code already does `logBody.prepend(tr)`). Prepending at the top of the DOM while the user is pinned to **visual** bottom is safe; when the user is **reading history** (PAUSED), prepending above the viewport **must not shift it** → the scroll container is bottom-anchored by content, so new rows appear *above* the current scroll position and `scrollTop` is unchanged because the user is not at the top… **this is the subtle bug:** prepending at the top *does* shift existing content down visually when scrolled into the middle. Rule: when not STICKY, suppress the visual shift by **re-applying `scrollTop += newBlockHeight`** in the same rAF frame as the prepend (classic "preserve scroll position on insert" fix, `debounce-throttle` class). Simpler alternative if virtualized: see below.
- Fixed row height assumption is **broken by expandable JSON payloads** — so the virtualizer (below) must measure real heights; do not hardcode.
- Empty-state, load-more `<tfoot>` (S6): pre-reserve the tfoot slot (it's already `display:none` → reserve min-height so showing "Load N more" never pushes the toolbar).

### Touch targets (S4, High)
- `.row-action` buttons: **27×27 → 44×44 px** hit area (extend via padding/pseudo, keep 14 px glyph). Adjacent row buttons gap **1 px → 8 px** (use `::before` spacing, not visual margin, so glyph row stays tight). `.toggle`, `.btn-sm`, `#clearBtn` all 44 px min height; ≥ 8 px between them. Mobile (<680 px card view) enlarges targets (S4 "Larger buttons on mobile").
- 24 px is the hard web floor; 44 is the on-touch/keyboard-friendly target the task specifies.

### Performance & DOM cap
- **DOM cap: keep 200–500 rows.** The code already pages via `state.pageSize` + "Load more" (older entries) and a separate SSE append. Add: when `#logBody.children.length` exceeds **400**, drop oldest *visible* rows (the ones furthest from the read head) — **exit faster than enter (S13): removal is instant, no exit animation** — and rely on the "Load more" tfoot + server history for access. Never silently drop rows the user can still scroll to; announce count via `visibleCount`.
- **Virtualize if > 500** (S14, High): move the stream table into the React island (`frontend/`) and render with `react-window`/`react-virtual` (fixed `rowHeight` estimate + dynamic measurement for expanded payloads). Stable `key={log.id}` (S14 "never index"). If it stays vanilla: the 400-cap + rAF-batched inserts are the floor; virtualization is the ceiling.
- **Scroll/insert throttling (S15: no DB match — general web practice, flagged):** batch DOM appends with `requestAnimationFrame`; for bursts (> N entries/frame from SSE), coalesce into one fragment per frame and pin the bottom once, not per entry. Existing `scrollToBottomOfList()` is already rAF-wrapped — extend it to also **debounce** the "user scrolled up → PAUSED" detection to ~50 ms so a fling doesn't toggle state per wheel tick.
- **`font-display: swap` + a mono fallback metric** (S6 "Font Loading"): reserve the panel height; mono fallback `ui-monospace, SFMono-Regular, Menlo` to avoid FOUT shift in the 13 px data column.
- **reduced-motion** (S9/S12): gate all of B's animations + the LIVE pulse behind `matchMedia('(prefers-reduced-motion: reduce)')`; kill any looping tween on unmount/`visibilitychange` (S12).

---

## D. Accessibility

- **Live region**: a **single** `role="status"` / `aria-live="polite"` node announcing *contextual* summaries (S5/S8), e.g. "12 new logs" — **not** a bare number and not per-entry (S5 anti-pattern "announcing a bare number"). **Suppress while the user is reading history (PAUSED/OFF)** — set the region `aria-live="off"` or simply don't update it, and re-enable on resume. Announce the jump-pill state change ("Auto-scroll paused, 12 new") only on the user-initiated action.
- **Contrast ≥ 4.5:1** (S1 requires `contrast-text-4.5`): every text/level color above is verified ≥ 6:1 on `#11141b`; on-accent `#04121a` on `#22d3ee` = 10.5:1.
- **Keyboard** (S7):
  - Panel is a focusable scroll region. **End** → jump to latest (same as pill); **Home** → top; **ArrowDown/Up** → line/row step; **Ctrl+End / Alt+ArrowDown** → toggle auto-scroll resume. Implement `keydown` on `#logContainer` (tabindex="0").
  - **Focus Not Obscured (AA, S7)**: sticky thead must not hide the focused row → add `scroll-padding-top: <thead height>` to the container; close the detail modal before returning focus so an overlay never covers `:focus`.
  - **Visible focus ring** on every control (S7 High; S1 checklist): `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }` (or the app's box-shadow ring at 3 px, `--ring` white); never `outline:none` without replacement.
- **Semantic structure** (S5 "Screen Reader"): rows as `<tr>` inside a real `<table>` (already the case), `scope="col"` on `th`; icon-only buttons keep `aria-label` (S8 High — the app already has them on row actions; verify the new pill + toggles get `aria-label`/`aria-pressed`).
- **LIVE indicator** (status dot): decorative `aria-hidden` on the dot, paired with a text `statusLabel` ("Connected / Disconnected") — never convey live status by a color dot alone (color-alone anti-pattern).
- **Reduced motion** respected (S9).

---

## E. Anti-patterns to avoid (from search results)

| Anti-pattern | Source |
|---|---|
| Auto-advance/auto-scroll with **no stop control** | S2 (High) |
| Animating **width/height** on entry; one duration for every transition | S13 / S1 |
| **No `prefers-reduced-motion`**; scroll-jacking / parallax nausea | S9 (High) |
| **Rendering thousands of DOM nodes** (unvirtualized stream) | S14 (High) |
| **Array index as list key** | S14 (High) |
| **Bare-number `aria-live`** / many competing live regions | S5 (High) |
| **Badge insertion that pushes the toolbar** (layout shift on new entries) | S6 (High) |
| **Touch targets < 44 px / < 8 px gap** | S4 (High/Med) |
| **Removing focus outlines without replacement**; sticky UI obscuring focus | S7 (High) |
| **Relying on color alone** to mark log level | chart/color rule (S11) |
| **Sub-12 px body text** in data rows | typography rule (S10/S3) |
| **Horizontal scroll** from wide mono payloads — keep `white-space:pre` + in-cell `overflow-x:auto`, never page-level | S2-result3 (High) |

---

## Notes on 0-result fallbacks (explicit, per skill contract)
- `virtualize lists` (ux), `list virtualize` (html-tailwind), `throttle` (react), `debounce throttle` (ux) → **all 0 results**. The virtualization + rAF/debounce guidance in §C is therefore sourced from the **react stack DB row "Virtualize long lists"** (real DB match, S14) for virtualization, and from the skill's `quick-reference.md §3` rows (`virtualize-lists`, `main-thread-budget`, `debounce-throttle`) + general web best practice for the throttle/rAF batching — **labeled here as non-DB fallback**, not presented as a database match.
- The `--design-system` PATTERN output (marketing hero/testimonial/CTA) was **off-topic for a dashboard** and discarded; per the skill's retry rule I applied only its style/color/typography/motion/effect/effect sections, which are on-topic.

Implementation is React/TS + CSS-ready: CSS custom properties already exist in `:root` (add the 4 level tokens + `--pending-pill`), the scroll model is ~1 hook/15 lines, and virtualization (if > 500) lands in the `frontend/` React island with `react-window` + `key={log.id}`.
