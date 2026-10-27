// A section's workspace: its PanelSpecs on a 24-column grid (8 px rows),
// laid out from the saved arrangement (halo.studio.layout.<section>) or the
// section's defaults, which fill the visible height until the user moves
// something. Floating panels sit over the grid. 3.3.2.0 R3: a section with a
// primary panel opens on it, the rest strips at the foot (quiet.ts);
// `?open=all` draws every panel in its spec's rectangle instead (a link, a capture).
import { useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "../store";
import { WorkspaceContext, type WorkspaceApi } from "./controller";
import { merge, openFirst, usedRows } from "./grid";
import { Panel } from "./Panel";
import { layoutStore, loadSaved, setLayout, registerSpecs } from "./persist";
import { FULL_PAGE } from "./quiet";
import { COLS, ROW, type PanelSpec } from "./types";

export { resetLayout, arrangeLayout, layoutStore, patchPanel, focusPanel, showPanel, hidePanel, LAYOUT_PREFIX } from "./persist";
export type { PanelSpec, Layout, PanelLayout, Face } from "./types";

/** `?open=media-status,media-render`: panels a link (or a capture) opens first, in a default arrangement only;
 *  `?open=all` (3.3.2.0 R3): every panel open in its spec's place, the full arrangement. */
const OPEN = (/[?&]open=([\w,-]+)/.exec(location.search)?.[1] || "").split(",").filter(Boolean);
const FULL = FULL_PAGE;

export function Workspace({ section, specs }: { section: string; specs: PanelSpec[] }) {
  const outer = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const { layout, custom } = useStore(layoutStore(section), (s) => s);
  const usedFill = useRef(0);
  const [height, setHeight] = useState(0);
  const [dragging, setDragging] = useState(false);
  registerSpecs(section, specs);

  useEffect(() => {
    const el = outer.current;
    if (!el) return;
    const measure = () => setHeight(el.clientHeight);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const fillRows = Math.max(0, Math.floor((height - 24) / ROW));
  useEffect(() => {
    // first draw, after a reset, and -- while the user has not rearranged anything -- on every resize
    if (fillRows > 0 && (!layout || (!custom && fillRows !== usedFill.current))) {
      usedFill.current = fillRows;
      const merged = merge(specs, custom ? loadSaved(section) : null, fillRows, FULL);
      setLayout(section, custom || FULL ? merged : openFirst(merged, OPEN, specs, fillRows), false);
    } else if (fillRows > 0 && layout && specs.some((s) => !s.optional && !layout[s.id])) {
      setLayout(section, merge(specs, layout, fillRows, FULL), false); // 3.2.0.0 R3: a pack's panel arrived: the rest stay put
    }
  }, [layout, custom, fillRows, section, specs]);

  const api = useMemo<WorkspaceApi>(
    () => ({
      section,
      specs,
      metrics: () => {
        const w = grid.current?.clientWidth || 1;
        const h = outer.current?.clientHeight || 1;
        return { width: w, height: h, colW: w / COLS, rows: Math.max(0, Math.floor((h - 24) / ROW)) }; // = fillRows below
      },
      setDragging,
    }),
    [section, specs],
  );

  const rows = layout ? usedRows(layout) : 0;
  return (
    <WorkspaceContext.Provider value={api}>
      <div className="workspace" ref={outer} data-dragging={dragging || undefined} data-section={section}>
        <div className="ws-grid" ref={grid} style={{ minHeight: Math.max(rows * ROW, height - 24) }}>
          {layout &&
            specs.map((spec) => (layout[spec.id] ? <Panel key={spec.id} spec={spec} p={layout[spec.id]} /> : null))}
        </div>
      </div>
    </WorkspaceContext.Provider>
  );
}
