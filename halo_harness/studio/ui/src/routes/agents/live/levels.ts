// Zoom that changes meaning (3.3.18.0 "The living canvas" part 4): three levels of Live, chosen by the zoom (and by the
// bar's three-way switch, which sets the zoom):
//
//   far   zoom under FAR_BELOW: blocks only -- the plan's blocks, or the tree's groups -- each with its count, state,
//         cost and the waiting marker, drawn FAR_SCALE times larger so they read at that zoom; no agent box
//   mid   today's boxes
//   near  zoom NEAR_FROM and up: each agent box grows by NEAR_H for its current thought (the THINK row's text, three
//         lines) and its running tool with its last output line
//
// The level changes only at those thresholds, and the thing under the pointer stays under it (zoomAnchor.ts). Fit picks
// the level that makes the whole session readable: the middle one when the tree fits at FAR_BELOW or more, else far
// (never under FAR_MIN).
import { createStore, useStore } from "../../../lib/store";

export type Level = "far" | "mid" | "near";
export const FAR_BELOW = 0.6;
export const NEAR_FROM = 1.3;
export const FAR_SCALE = 2;
export const FAR_MIN = 0.45; // Fit never goes under it: a far block's words stay 11 px or more on screen (it scrolls instead)
export const NEAR_H = 78; // the thought (three lines) and the tool's last output line
export const LEVEL_ZOOM: Record<Level, number> = { far: 0.5, mid: 1, near: 1.5 };

export const levelOf = (zoom: number): Level => (zoom < FAR_BELOW ? "far" : zoom >= NEAR_FROM ? "near" : "mid");

/** `?level=far|mid|near` pins the level whatever the zoom (a capture's or a driver's door) until the switch is used. */
function urlLevel(): Level | null {
  try {
    const v = new URLSearchParams(location.search).get("level");
    return v === "far" || v === "mid" || v === "near" ? v : null;
  } catch {
    return null;
  }
}
const pin = createStore<{ level: Level | null }>({ level: urlLevel() });
export const usePinnedLevel = (): Level | null => useStore(pin, (s) => s.level);
export const unpinLevel = (): void => pin.update((s) => (s.level ? { level: null } : {}));

/** The level Live draws now (the nodes read it for their near rows). */
export const levelStore = createStore<{ level: Level }>({ level: "mid" });
export const useLevel = (): Level => useStore(levelStore, (s) => s.level);
export const setLevel = (level: Level): void => levelStore.update((s) => (s.level === level ? {} : { level }));

/** Fit: the zoom that shows `w` x `h` (mid) in a `vw` x `vh` view; when that is under FAR_BELOW, the far drawing's
 *  (`fw` x `fh`, already FAR_SCALE larger) fitted and held under FAR_BELOW. */
export function fitZoom(vw: number, vh: number, w: number, h: number, fw: number, fh: number, max = 1.25): number {
  const mid = Math.min(max, (vw - 24) / w, (vh - 24) / h);
  if (mid >= FAR_BELOW) return mid;
  return Math.max(FAR_MIN, Math.min(FAR_BELOW - 0.01, (vw - 24) / fw, (vh - 24) / fh));
}
