// The stage's controller (3.6.0.0 R0a): the workspace context, a drawer's splitter (pointer events with pointer
// capture, no library) and its keys. Panels no longer move: a drawer is resized from its inner edge or with
// Alt+Left / Alt+Right on it (widen / narrow by 40 px, 360-560 px); what is open is the view bar's.
import { createContext, useContext, type KeyboardEvent, type PointerEvent } from "react";
import { layoutStore, setLayout } from "./persist";
import { roleOf, sideOf } from "./rules";
import { DRAWER_MAX, DRAWER_MIN, DRAWER_STEP, type PanelSpec } from "./types";

export type WorkspaceApi = {
  section: string;
  specs: PanelSpec[];
  /** The stage's box in px. */
  metrics: () => { width: number; height: number };
};

export const WorkspaceContext = createContext<WorkspaceApi | null>(null);

export function useWorkspace(): WorkspaceApi {
  const ws = useContext(WorkspaceContext);
  if (!ws) throw new Error("useWorkspace outside a <Workspace>");
  return ws;
}

const clampW = (w: number) => Math.max(DRAWER_MIN, Math.min(DRAWER_MAX, Math.round(w)));

/** A drawer's width set by hand (a person's choice: kept, R10). */
export function setDrawerWidth(section: string, id: string, px: number, save = true): void {
  const cur = layoutStore(section).get().layout;
  if (!cur || !cur[id]) return;
  setLayout(section, { ...cur, [id]: { ...cur[id], width: clampW(px) } }, save);
}

/** onPointerDown for a drawer's splitter: its inner edge follows the pointer. */
export function useSplitter(spec: PanelSpec, startW: number) {
  const ws = useWorkspace();
  return (ev: PointerEvent<HTMLElement>) => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    const el = ev.currentTarget;
    el.setPointerCapture(ev.pointerId);
    const sx = ev.clientX;
    const dir = sideOf(spec) === "right" ? -1 : 1; // a right drawer widens to the left
    let last = startW;
    const onMove = (e: globalThis.PointerEvent) => {
      last = clampW(startW + dir * (e.clientX - sx));
      setDrawerWidth(ws.section, spec.id, last, false);
    };
    const onUp = () => {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
      if (last !== startW) setDrawerWidth(ws.section, spec.id, last, true);
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
  };
}

/** Alt+Left / Alt+Right on a focused drawer widen or narrow it (toward the main thing widens). */
export function usePanelKeys(id: string) {
  const ws = useWorkspace();
  return (ev: KeyboardEvent<HTMLElement>) => {
    if (!ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) return;
    if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
    if (ev.target !== ev.currentTarget && (ev.target as HTMLElement).closest("input, textarea, select")) return;
    const spec = ws.specs.find((s) => s.id === id);
    const p = layoutStore(ws.section).get().layout?.[id];
    if (!spec || !p || roleOf(spec) !== "drawer" || p.collapsed) return;
    ev.preventDefault();
    ev.stopPropagation();
    const toward = (sideOf(spec) === "right") === (ev.key === "ArrowLeft");
    const now = (ev.currentTarget.closest(".ws-cell") as HTMLElement | null)?.getBoundingClientRect().width || p.width || DRAWER_MIN;
    setDrawerWidth(ws.section, id, now + (toward ? DRAWER_STEP : -DRAWER_STEP));
  };
}
