// The stage's controller (3.6.0.0 R0a): the workspace context, a drawer's splitter (pointer events with pointer
// capture, no library) and its keys. Panels no longer move: a drawer is resized from its inner edge or with
// Alt+Left / Alt+Right on it (widen / narrow by 40 px, 360-560 px); what is open is the view bar's.
// 3.6.0.0 R4b (the owner: "that line in the middle ... doesn't move"): a drawer that holds a drawing drags until the
// main thing is MAIN_MIN wide (rules.ts drawerMax, the stage writes it on the drawer as `data-max`); a drag that loses
// its pointer capture (an iframe, a window switch) ends like a release; while it drags no drawing re-fits
// (canvasNav.holdFits). Alt+Up on a panel: Only this (again: Show both); Alt+Down: Show both.
import { createContext, useContext, type KeyboardEvent, type PointerEvent } from "react";
import { holdFits } from "../canvasNav";
import { layoutStore, setLayout, showBoth, showOnly } from "./persist";
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

const clampW = (w: number, max = DRAWER_MAX) => Math.max(DRAWER_MIN, Math.min(Math.max(DRAWER_MIN, max), Math.round(w)));

/** A drawer's width set by hand (a person's choice: kept, R10), at most `max` (a drawing's drawer: rules.drawerMax). */
export function setDrawerWidth(section: string, id: string, px: number, save = true, max = DRAWER_MAX): void {
  const cur = layoutStore(section).get().layout;
  if (!cur || !cur[id]) return;
  setLayout(section, { ...cur, [id]: { ...cur[id], width: clampW(px, max) } }, save);
}

/** onPointerDown for a drawer's splitter: its inner edge follows the pointer, up to `max` px. */
export function useSplitter(spec: PanelSpec, startW: number, max: number) {
  const ws = useWorkspace();
  return (ev: PointerEvent<HTMLElement>) => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    const el = ev.currentTarget;
    el.setPointerCapture(ev.pointerId);
    const sx = ev.clientX;
    const dir = sideOf(spec) === "right" ? -1 : 1; // a right drawer widens to the left
    let last = startW;
    holdFits(true);
    document.documentElement.dataset.resizing = "1"; // workspace.css: no iframe takes the pointer meanwhile
    const onMove = (e: globalThis.PointerEvent) => {
      last = clampW(startW + dir * (e.clientX - sx), max);
      setDrawerWidth(ws.section, spec.id, last, false, max);
    };
    const onUp = () => {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
      el.removeEventListener("lostpointercapture", onUp);
      delete document.documentElement.dataset.resizing;
      if (last !== startW) setDrawerWidth(ws.section, spec.id, last, true, max);
      holdFits(false); // once the last width is drawn: a drawing not zoomed by hand fits once
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
    el.addEventListener("lostpointercapture", onUp);
  };
}

/** Alt+Left / Alt+Right on a focused drawer widen or narrow it (toward the main thing widens); Alt+Up shows the focused
 *  panel alone (Only this; again: Show both), Alt+Down shows both again. */
export function usePanelKeys(id: string) {
  const ws = useWorkspace();
  return (ev: KeyboardEvent<HTMLElement>) => {
    if (!ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) return;
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(ev.key)) return;
    if (ev.target !== ev.currentTarget && (ev.target as HTMLElement).closest("input, textarea, select")) return;
    const spec = ws.specs.find((s) => s.id === id);
    const st = layoutStore(ws.section).get();
    const p = st.layout?.[id];
    if (!spec || !p) return;
    if (ev.key === "ArrowUp" || ev.key === "ArrowDown") {
      if (roleOf(spec) === "dock") return;
      ev.preventDefault();
      ev.stopPropagation();
      if (ev.key === "ArrowDown" || st.solo === id) showBoth(ws.section);
      else showOnly(ws.section, id);
      return;
    }
    if (roleOf(spec) !== "drawer" || p.collapsed || st.solo === id) return;
    ev.preventDefault();
    ev.stopPropagation();
    const toward = (sideOf(spec) === "right") === (ev.key === "ArrowLeft");
    const drawer = ev.currentTarget.closest(".stage-drawer") as HTMLElement | null;
    const now = drawer?.getBoundingClientRect().width || p.width || DRAWER_MIN;
    setDrawerWidth(ws.section, id, now + (toward ? DRAWER_STEP : -DRAWER_STEP), true, Number(drawer?.dataset.max) || DRAWER_MAX);
  };
}
