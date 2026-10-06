import React from "react";
import { createRoot, type Root } from "react-dom/client";

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

function Diagram({ json, theme }: MountOptions) {
  const [Comp, setComp] = React.useState<JsonCrackComponent | null>(null);
  const [error, setError] = React.useState<string | null>(null);

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
    <Comp
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
