// Where each box and line of the map sits (3.6.0.0 R3, the design's "Reading"): main at the left; a box's column is its
// longest chain of lines from main, so every line runs left to right; a box nothing hands work to waits under the map
// ("Not connected yet", not drawn here). Between two columns runs the label lane: each line's When is a label there, just
// above where the line enters its box, never over a box; lines from one box share one trunk (a vertical just right of
// it). A box is as tall as its text (measured once drawn: boxes never squish) and at least as tall as its labels.
import type { DrawBox, DrawLine } from "./mapTypes";

export const BOX_W = 248;
export const LANE = 212;
export const LABEL_W = 176;
export const LABEL_H = 28;
export const PAD = 24;
const GAP = 28;
const STEP = 34; // one more line into the same box: its label and its line this much lower
const ENTER = 30; // where the first line enters a box, from its top

export type Placed = DrawBox & { x: number; y: number; h: number; col: number };
export type Routed = DrawLine & { d: string; lx: number; ly: number; key: string };

export function estimate(b: DrawBox, open: boolean, steps: number): number {
  const name = Math.max(1, Math.ceil(b.name.length / 28));
  return 64 + name * 19 + (open ? 30 + steps * 20 : 0);
}

/** The columns: main 0, every other box on the map one more than its deepest source (no circle: the format refuses one). */
export function columns(boxes: DrawBox[], lines: DrawLine[]): Map<string, number> {
  const col = new Map<string, number>([["main", 0]]);
  const on = new Set(boxes.map((b) => b.id));
  for (let pass = 0; pass < boxes.length + 1; pass++) {
    let moved = false;
    for (const l of lines) {
      if (!on.has(l.to) || !col.has(l.from)) continue;
      const want = (col.get(l.from) || 0) + 1;
      if ((col.get(l.to) ?? -1) < want) {
        col.set(l.to, want);
        moved = true;
      }
    }
    if (!moved) break;
  }
  return col;
}

export function layout(boxes: DrawBox[], lines: DrawLine[], height: (b: DrawBox) => number) {
  const col = columns(boxes, lines);
  const drawn = boxes.filter((b) => col.has(b.id));
  const into = new Map<string, DrawLine[]>();
  for (const l of lines) if (col.has(l.to) && col.has(l.from)) into.set(l.to, [...(into.get(l.to) || []), l]);
  const byCol = new Map<number, DrawBox[]>();
  for (const b of drawn) byCol.set(col.get(b.id)!, [...(byCol.get(col.get(b.id)!) || []), b]);
  const placed = new Map<string, Placed>();
  const ncols = Math.max(1, ...[...byCol.keys()].map((c) => c + 1));
  let bottom = 0;
  for (let c = 0; c < ncols; c++) {
    const here = byCol.get(c) || [];
    const srcY = (b: DrawBox) => Math.min(...(into.get(b.id) || []).map((l) => placed.get(l.from)?.y ?? 1e6), 1e6);
    here.sort((a, b) => srcY(a) - srcY(b));
    let y = PAD + (c === 0 ? 0 : 0);
    for (const b of here) {
      const n = (into.get(b.id) || []).length;
      const h = Math.max(height(b), ENTER + STEP * Math.max(0, n - 1) + 24);
      placed.set(b.id, { ...b, x: PAD + c * (BOX_W + LANE), y, h, col: c });
      y += h + GAP;
    }
    bottom = Math.max(bottom, y);
  }
  const routed: Routed[] = [];
  for (const [to, ls] of into) {
    const t = placed.get(to)!;
    ls.forEach((l, k) => {
      const s = placed.get(l.from)!;
      const sx = s.x + BOX_W, sy = s.y + ENTER, trunk = sx + 18, ty = t.y + ENTER + STEP * k;
      routed.push({ ...l, key: `${l.from}>${l.to}`, d: `M${sx} ${sy} H${trunk} V${ty} H${t.x}`,
                    lx: t.x - LABEL_W - 10, ly: ty - LABEL_H - 2 });
    });
  }
  return { boxes: [...placed.values()], lines: routed, w: PAD * 2 + ncols * BOX_W + (ncols - 1) * LANE, h: Math.max(bottom - GAP + PAD, 160) };
}
