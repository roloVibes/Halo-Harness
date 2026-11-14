// The map as drawn while it is lit (3.6.0.0 R4): the same drawing (view.ts), with what the running session adds --
// each helper it made up as a dashed box beside the box that started it (one column right, a dashed line from it, no
// When label: no line was drawn for it), and a Builder card it parked drawn as the builder's own ghosts. A session that
// did not start on a map (or a replay of one) draws on an empty map: main and its helpers, no invented lines.
// 3.6.0.0 R4b: one level only -- a helper a helper started is counted on it ("+N under it"), listed in the drawer.
import type { Change } from "../types";
import { firstLevel, type Overlay } from "./overlay";
import type { DrawBox, DrawLine, MapFile } from "./mapTypes";
import type { MapView } from "./view";

/** The file the lit map draws: the map itself, or (`bare`) main alone. */
export function litFile(file: MapFile | null, bare: boolean): MapFile | null {
  return file && bare ? { ...file, boxes: [], lines: [] } : file;
}

/** The builder's pending rows plus a session's parked card (every line of it drawn, as its card shows them all). */
export function withCard(pending: Change[], card: Change[]): Change[] {
  return card.length ? [...pending, ...card.map((c) => ({ ...c, ticked: true }))] : pending;
}

export const helperId = (aid: string) => `made-up:${aid}`;

export function withLit(v: MapView, ov: Overlay | null): MapView {
  if (!ov || !ov.helpers.length) return v;
  const on = new Set(v.boxes.map((b) => b.id));
  const boxes: DrawBox[] = [...v.boxes];
  const lines: DrawLine[] = [...v.lines];
  for (const h of firstLevel(ov.helpers)) { // R4b: a helper's own helpers are its "+N under it", not a second level
    if (!on.has(h.box)) continue;
    const id = helperId(h.aid);
    boxes.push({ id, kind: "agent", name: h.name, names: [h.name], helper: h.aid });
    lines.push({ from: h.box, to: id, helper: true });
  }
  return { ...v, boxes, lines };
}
