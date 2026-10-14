// Drag / resize / keyboard controller for workspace panels: pointer events
// with pointer capture (no library). A grid panel snaps to cells as it moves
// and the others make room live; a floating panel moves in 8 px steps.
import { createContext, useContext, type KeyboardEvent, type PointerEvent } from "react";
import { applyDelta, applyDeltaPx, arrange, clampRect, effH } from "./grid";
import { layoutStore, setLayout } from "./persist";
import { COLS, MOVE_ROWS, ROW, type Gesture, type Layout, type PanelSpec } from "./types";

export type WorkspaceApi = {
  section: string;
  specs: PanelSpec[];
  /** Workspace content box in px. */
  metrics: () => { width: number; height: number; colW: number };
  setDragging: (on: boolean) => void;
};

export const WorkspaceContext = createContext<WorkspaceApi | null>(null);

export function useWorkspace(): WorkspaceApi {
  const ws = useContext(WorkspaceContext);
  if (!ws) throw new Error("useWorkspace outside a <Workspace>");
  return ws;
}

function current(section: string): Layout | null {
  return layoutStore(section).get().layout;
}

function raise(layout: Layout, id: string): Layout {
  const top = Object.values(layout).reduce((m, p) => Math.max(m, p.z || 0), 0);
  return layout[id].z === top && top > 0 ? layout : { ...layout, [id]: { ...layout[id], z: top + 1 } };
}

/** onPointerDown for a title bar ("move") or a resize handle. */
export function useGesture(id: string, g: Gesture) {
  const ws = useWorkspace();
  return (ev: PointerEvent<HTMLElement>) => {
    if (ev.button !== 0) return;
    if (g === "move" && (ev.target as HTMLElement).closest("button, input, select, a")) return;
    const start = current(ws.section);
    if (!start || !start[id]) return;
    ev.preventDefault();
    const el = ev.currentTarget;
    el.setPointerCapture(ev.pointerId);
    const p0 = start[id];
    const spec = ws.specs.find((s) => s.id === id);
    const { colW, width, height } = ws.metrics();
    const sx = ev.clientX;
    const sy = ev.clientY;
    let lastKey = "";
    let moved = false; // a press without a move (a click to focus the panel) changes nothing
    ws.setDragging(true);
    const base = raise(start, id);
    const onMove = (e: globalThis.PointerEvent) => {
      const dxPx = e.clientX - sx;
      const dyPx = e.clientY - sy;
      if (!moved && Math.abs(dxPx) < 3 && Math.abs(dyPx) < 3) return;
      moved = true;
      let next: Layout;
      if (p0.floating) {
        const r = applyDeltaPx({ x: p0.fx, y: p0.fy, w: p0.fw, h: p0.fh }, g, dxPx, dyPx, { w: width, h: height });
        next = { ...base, [id]: { ...base[id], fx: r.x, fy: r.y, fw: r.w, fh: r.h } };
      } else {
        const r = applyDelta(p0, g, Math.round(dxPx / colW), Math.round(dyPx / ROW), spec);
        const key = `${r.x},${r.y},${r.w},${r.h}`;
        if (key === lastKey) return;
        lastKey = key;
        next = arrange({ ...base, [id]: { ...base[id], ...r } }, id, true);
      }
      setLayout(ws.section, next, false);
    };
    const onUp = () => {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
      ws.setDragging(false);
      const end = current(ws.section);
      if (end && moved) setLayout(ws.section, p0.floating ? end : arrange(end), true);
      else if (end && p0.floating) setLayout(ws.section, raise(end, id), false); // a click brings a floating panel to the front
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
  };
}

/** Alt+arrows move the focused panel; Alt+Shift+arrows resize it. */
export function usePanelKeys(id: string) {
  const ws = useWorkspace();
  return (ev: KeyboardEvent<HTMLElement>) => {
    if (!ev.altKey || ev.ctrlKey || ev.metaKey) return;
    const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[ev.key];
    if (!dir) return;
    if (ev.target !== ev.currentTarget && (ev.target as HTMLElement).closest("input, textarea, select")) return;
    const layout = current(ws.section);
    if (!layout || !layout[id]) return;
    ev.preventDefault();
    ev.stopPropagation();
    const p = layout[id];
    const spec = ws.specs.find((s) => s.id === id);
    const [dx, dy] = dir;
    if (p.floating) {
      const { width, height } = ws.metrics();
      const g: Gesture = ev.shiftKey ? "se" : "move";
      const r = applyDeltaPx({ x: p.fx, y: p.fy, w: p.fw, h: p.fh }, g, dx * 32, dy * 32, { w: width, h: height });
      setLayout(ws.section, { ...layout, [id]: { ...p, fx: r.x, fy: r.y, fw: r.w, fh: r.h } });
      return;
    }
    if (!ev.shiftKey && dy) {
      setLayout(ws.section, arrange(swapVertical(layout, id, dy)));
      return;
    }
    const r = ev.shiftKey
      ? clampRect({ ...p, w: p.w + dx, h: p.h + dy * MOVE_ROWS }, spec)
      : clampRect({ ...p, x: p.x + dx }, spec);
    if (r.x + r.w > COLS) return;
    setLayout(ws.section, arrange({ ...layout, [id]: { ...p, ...r } }, id));
  };
}

/** Alt+Up/Down on a compacted grid: trade places with the nearest panel above / below in the same columns. */
function swapVertical(layout: Layout, id: string, dy: number): Layout {
  const p = layout[id];
  const cols = (q: Layout[string]) => q.x < p.x + p.w && p.x < q.x + q.w;
  const others = Object.entries(layout).filter(([k, q]) => k !== id && !q.floating && cols(q));
  const pick = dy > 0
    ? others.filter(([, q]) => q.y > p.y).sort((a, b) => a[1].y - b[1].y)[0]
    : others.filter(([, q]) => q.y < p.y).sort((a, b) => b[1].y - a[1].y)[0];
  if (!pick) return layout;
  const [qid, q] = pick;
  const top = Math.min(p.y, q.y);
  const [first, second] = dy > 0 ? [q, p] : [p, q];
  const firstId = dy > 0 ? qid : id;
  const secondId = dy > 0 ? id : qid;
  return { ...layout, [firstId]: { ...first, y: top }, [secondId]: { ...second, y: top + effH(first) } };
}
