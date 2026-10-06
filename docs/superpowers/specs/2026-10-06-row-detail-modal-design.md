# Row Detail Modal — Design

**Date:** 2026-10-06
**Status:** Approved
**Feature:** Per-row detail view with a keys tree and a JSON diagram

## Problem

Each log row shows a compact payload preview and an expandable raw JSON body.
There is no way to inspect a payload's *structure* — the keys, their types and
nesting — without reading raw JSON. The row action cell also duplicates the
payload copy that already exists on the expanded payload body.

## Goals

1. Replace the row's **copy payload** action with a **Detail** action.
2. A modal with two tabs:
   - **Keys** — the payload's keys and values rendered as an informational,
     expandable tree (not raw JSON).
   - **Diagram** — a node-link diagram of the JSON structure.
3. A **browser-viewport fullscreen** toggle for the modal (not the OS Fullscreen
   API).
4. Everything works for arbitrarily shaped payloads — the key set differs per
   row, so the rendering must be fully dynamic.

## Constraints

- **Zero external dependencies.** `main.py` mounts no static directory and the
  README promises "no build tools needed, single-file frontend". No CDN scripts.
  The diagram is hand-rolled SVG inside `static/index.html`.
- **Payload is untrusted.** It originates from arbitrary webhooks. All values are
  written with `textContent` / `escapeHtml`, never `innerHTML` — including
  inside SVG.
- **Theme-aware.** Colors come from the existing CSS custom properties so the
  light/dark toggle recolors the modal and diagram for free.

## Non-goals

- Server-side changes.
- Horizontal diagram orientation.
- Exporting the diagram as an image.

## Architecture

### Shared unit: the tree model

Both tabs consume one pure function. This is the seam that keeps them
independent and separately testable.

```js
buildTree(payload) -> TreeNode
TreeNode = {
  key: string,          // property name, "[i]" for array items, "root" at top
  path: string,         // dotted/bracketed path from the root, for copy + ids
  kind: 'object'|'array'|'string'|'number'|'boolean'|'null',
  value: any,           // scalars only
  size: number,         // child count, containers only
  children: TreeNode[]  // containers only
}
```

Neither renderer inspects the raw payload; both walk this model.

### Components

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `buildTree(payload)` | Normalize any JSON value into `TreeNode` | — |
| `renderKeysTree(tree)` | Indented expandable rows | tree model, `.type-*` badges |
| `layoutTree(root)` | Tidy tree layout → `{nodes, edges, width, height}` | tree model |
| `renderDiagram(tree)` | SVG nodes + bézier edges from the layout | `layoutTree` |
| Modal controller | open/close, tabs, fullscreen, focus trap | DOM only |

### Keys tab

Indented tree, expand/collapse per node. Each row: disclosure control, key, type
badge, value. Containers show `{n}` / `[n]`; leaves show the value with ellipsis
truncation plus a `title`. A copy-value affordance per leaf. Opens with two
levels expanded, deeper nodes collapsed. Type badges reuse the existing
`.payload-type-badge` / `.type-*` classes.

### Diagram tab

**Layout:** Reingold–Tilford tidy tree. Leaves take sequential x-slots; parents
center over their children; depth maps to y. Only *expanded* nodes are laid out,
which keeps large payloads cheap on open (the lazy-render guard). Node width is
measured with an offscreen canvas `measureText`, so boxes fit content without a
DOM round-trip.

**Rendering:** rounded rect per node (key + value), collapse toggle on
containers, root emphasized with the accent. Cubic bézier edges at low-opacity
ink. A subtle dot grid on the background. All colors via CSS classes, never
inline `fill` attributes.

**Interaction:** click a node to collapse/expand; wheel zooms about the pointer;
drag pans; a floating control pill offers zoom-in / zoom-out / fit / expand-all /
collapse-all. Opens expanded 1–2 levels.

### Modal shell

- Centered by default: `min(920px, 92vw)` × `min(640px, 88dvh)`.
- Fullscreen is a CSS class filling `100dvw`/`100dvh` (`dvh`, not `100vh`, for
  mobile browser chrome).
- Header: `#id Detail`, tabs, maximize toggle, close.
- **Escape:** in fullscreen → exit fullscreen; otherwise → close.
- **A11y:** `role="dialog"`, `aria-modal="true"`, focus trap with Tab cycling,
  focus restored to the triggering button on close, scrim click closes.
- **Tabs:** `role="tablist"` / `tab` / `tabpanel`, `aria-selected`, Left/Right
  arrow navigation.

### Row action change

`buildActionsCell` becomes **Detail · Copy row · Delete**. Copy-payload is
removed from the action row (it already exists on the expanded payload body).

## Data flow

```
row Detail button --data-id--> find log in state.logs
  -> buildTree(log.payload)
     -> Keys tab:    renderKeysTree(tree)
     -> Diagram tab: layoutTree(tree) -> renderDiagram()
```

The tree is rebuilt per open; collapse state lives in the modal, not in `state`.

## Error handling

- Non-container payloads (string/number/boolean/null) render as a single-node
  tree and a one-node diagram — no special-casing required.
- Empty `{}` / `[]` render a container node with `{0}` / `[0]` and no children.
- Cyclic structures cannot occur (payloads come from JSON over the wire), but
  layout is still bounded by a max-depth guard to keep deep payloads finite.

## Testing

CDP harness against the real `index.html` and a seeded mock API:

- Modal opens from the Detail action; closes via scrim, close button, Escape.
- Tabs switch; keyboard arrow navigation; `aria-selected` follows.
- Keys tree expands/collapses; nested rows appear/disappear.
- Diagram node count drops when a subtree is collapsed; zoom changes the
  transform; expand-all/collapse-all work.
- Fullscreen class applies; Escape exits fullscreen first, then closes.
- Focus trap cycles within the modal; focus returns to the Detail button.
- Theme switch recolors the diagram (computed fill changes).
- Injection: keys/values containing `<script>`, quotes and unicode render as
  text, never as markup.

## Trade-off

Adds ~450–550 lines to `static/index.html` (≈1850 → ≈2400). Large for one file,
but the direct consequence of the single-file/no-build promise. Splitting into
served modules would be cleaner engineering but changes the backend and the
project's stated identity, so it is deliberately out of scope.
