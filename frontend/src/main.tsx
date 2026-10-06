import React from "react";
import { createRoot, type Root } from "react-dom/client";
import type { JSONCrackRef } from "jsoncrack-react";

/**
 * React island that renders the JSON Crack graph inside the HookView detail
 * modal. The host page owns the payload, the theme and the fullscreen state,
 * and drives this component through a tiny imperative API exposed on
 * window.HookViewDiagram.
 */

type Theme = "dark" | "light";

interface MountOptions {
  /** Payload to visualize. Any JSON value. */
  json: unknown;
  /** Theme, kept in sync with the host page's light/dark toggle. */
  theme: Theme;
}

const MAX_NODES = 1500;

type JsonCrackComponent = React.ComponentType<{
  ref?: React.Ref<JSONCrackRef>;
  json: object;
  theme: Theme;
  layoutDirection: string;
  showControls: boolean;
  showGrid: boolean;
  maxRenderableNodes: number;
  renderNodeLimitExceeded: (count: number, max: number) => React.ReactNode;
  onParseError: (err: Error) => void;
}>;

// jsoncrack-react pulls in elkjs, reablocks and motion — roughly 1.3MB
// gzipped. Importing it lazily keeps it out of the entry bundle, so the page
// pays for it only when the Diagram tab is first opened.
let componentPromise: Promise<JsonCrackComponent> | null = null;
function loadComponent(): Promise<JsonCrackComponent> {
  if (!componentPromise) {
    componentPromise = Promise.all([
      import("jsoncrack-react"),
      import("jsoncrack-react/style.css"),
    ]).then(([mod]) => mod.JSONCrack as unknown as JsonCrackComponent);
  }
  return componentPromise;
}

/** Union of the drawn node-card boxes, in viewport coordinates. */
function graphBounds(host: HTMLElement): DOMRect | null {
  const rects = [...host.querySelectorAll("g rect")]
    .map((r) => r.getBoundingClientRect())
    .filter((r) => r.width > 0 && r.height > 0);
  if (!rects.length) return null;
  const left = Math.min(...rects.map((r) => r.left));
  const right = Math.max(...rects.map((r) => r.right));
  const top = Math.min(...rects.map((r) => r.top));
  const bottom = Math.max(...rects.map((r) => r.bottom));
  return new DOMRect(left, top, right - left, bottom - top);
}

function Diagram({ json, theme }: MountOptions) {
  const [Comp, setComp] = React.useState<JsonCrackComponent | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const ref = React.useRef<JSONCrackRef | null>(null);
  const hostRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    let alive = true;
    loadComponent()
      .then((c) => {
        if (alive) setComp(() => c);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, []);

  // Fit the graph to the host box.
  //
  // `centerView()` is jsoncrack's own fit: it scales to fit and re-centers, and
  // it is idempotent, so calling it again on a resize is safe. `setZoom` is NOT
  // absolute — it multiplies the current scale — and the transform is applied
  // asynchronously, so correcting the zoom by measuring in the same tick reads
  // stale bounds and compounds badly. Plain centerView() is both correct and
  // exactly what the built-in "Fit" control does.
  const fitToView = React.useCallback(() => {
    if (!hostRef.current || !ref.current) return;
    try {
      ref.current.centerView();
    } catch {
      /* viewport not ready; the caller retries */
    }
  }, []);

  // Fit on first show.
  //
  // The module load, the tab reveal and the modal's width transition are all
  // async. Fitting while jsoncrack is still laying out fights the layout and
  // produces a badly wrong zoom, so wait until the drawn graph has held the
  // same size for a couple of frames — i.e. layout has settled — then fit once.
  React.useEffect(() => {
    if (!Comp) return;
    const deadline = Date.now() + 4000;
    let raf = 0;
    let prevSig = "";
    let stable = 0;
    const tick = () => {
      const host = hostRef.current;
      const bounds = host ? graphBounds(host) : null;
      const sig = bounds ? `${Math.round(bounds.width)}x${Math.round(bounds.height)}` : "";
      stable = sig && sig === prevSig ? stable + 1 : 0;
      prevSig = sig;
      if (bounds && stable >= 2) {
        fitToView();
        return;
      }
      if (Date.now() < deadline) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [Comp, fitToView, json]);

  // Re-fit when the host box changes size — entering or leaving fullscreen, a
  // window resize, or a device rotation. Without this the graph keeps the zoom
  // it was first fitted at and sits small in the larger viewport.
  // `Comp` is a dependency because the host div only mounts once the component
  // has loaded; without it this effect would run against a null ref and never
  // observe anything.
  React.useEffect(() => {
    const host = hostRef.current;
    if (!host || typeof ResizeObserver === "undefined") return;
    let last = { w: 0, h: 0 };
    let timer = 0;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (!r || !r.width || !r.height) return;
      if (r.width === last.w && r.height === last.h) return;
      last = { w: r.width, h: r.height };
      // The modal animates its width, so settle before measuring.
      window.clearTimeout(timer);
      timer = window.setTimeout(fitToView, 140);
    });
    ro.observe(host);
    return () => {
      window.clearTimeout(timer);
      ro.disconnect();
    };
  }, [Comp, fitToView]);

  if (error) {
    return (
      <div className="hv-limit">
        <strong>Diagram failed to load</strong>
        <span>{error}</span>
      </div>
    );
  }

  if (!Comp) {
    return (
      <div className="hv-limit">
        <span>Loading diagram…</span>
      </div>
    );
  }

  return (
    <div ref={hostRef} style={{ width: "100%", height: "100%" }}>
      <Comp
        ref={ref}
        json={json as object}
        theme={theme}
        layoutDirection="RIGHT"
        showControls
        showGrid
        maxRenderableNodes={MAX_NODES}
        renderNodeLimitExceeded={(count: number, max: number) => (
          <div className="hv-limit">
            <strong>Too many nodes to draw</strong>
            <span>
              This payload expands to {count.toLocaleString()} nodes (limit{" "}
              {max.toLocaleString()}). Use the Keys tab to inspect it, or collapse a
              branch there first.
            </span>
          </div>
        )}
        onParseError={(err: Error) => {
          // eslint-disable-next-line no-console
          console.error("[hookview] diagram parse error:", err);
        }}
      />
    </div>
  );
}

let root: Root | null = null;

/**
 * Mount or update the diagram. Calling this repeatedly with a new payload
 * re-renders in place rather than remounting, so the canvas and its camera
 * survive payload changes.
 */
function mount(container: HTMLElement, options: MountOptions) {
  if (!root) root = createRoot(container);
  root.render(<Diagram {...options} />);
}

function unmount() {
  if (root) {
    root.unmount();
    root = null;
  }
}

declare global {
  interface Window {
    HookViewDiagram?: {
      mount: (container: HTMLElement, options: MountOptions) => void;
      unmount: () => void;
    };
  }
}

// The host page is plain vanilla JS, so expose a minimal global API rather
// than expecting it to import this module.
window.HookViewDiagram = { mount, unmount };

export {};
