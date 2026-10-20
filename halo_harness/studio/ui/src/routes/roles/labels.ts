// Where the Roles canvas puts its edge labels (3.1.6.0 R1; the owner's
// one-tier lineup read as main -> worker -> media because the routing words
// sat on top of each other at the edges' midpoints): each label sits along
// its edge, offset by its index among the edges leaving the same card (the
// k-th of n at 30..70% of the way), then nudged along the edge until its box
// is clear of every label already placed and, when it can be, of the cards.
// The selected card's edges and the pipeline's are placed first; a label
// that still collides is dropped (a non-selected delegation edge's first),
// so no two label boxes ever overlap.
import { CARD_H, CARD_W, curveAt, type Box, type Curve } from "./layout";

export type LabelIn = { key: string; from: string; text: string; c: Curve; keep: boolean; order: number };
export type LabelOut = { x: number; y: number; box: Box };

// 10.5 px mono: about 0.6em a character; the box is a little wider and taller than the glyphs
const CHAR_W = 6.7;
const PAD_X = 4;
const ASCENT = 11;
const DESCENT = 4;

/** The world box of a label whose text is centred on (x, y) (y is the baseline). */
export function labelBox(text: string, x: number, y: number): Box {
  const w = text.length * CHAR_W + PAD_X * 2;
  return { x: x - w / 2, y: y - ASCENT, w, h: ASCENT + DESCENT };
}

const hit = (a: Box, b: Box) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/** The fractions along the edge to try, nearest the label's own slot first. */
function tries(base: number): number[] {
  const out = [base];
  for (let d = 0.07; d <= 0.36; d += 0.07) out.push(base + d, base - d);
  return out.filter((t) => t >= 0.14 && t <= 0.86);
}

/** Each label's spot (absent: dropped). `cards` are the card positions on the canvas, kept clear when they can be. */
export function placeLabels(items: LabelIn[], cards: { x: number; y: number }[]): Record<string, LabelOut> {
  const siblings: Record<string, LabelIn[]> = {};
  for (const it of items) (siblings[it.from] ||= []).push(it);
  const slotOf: Record<string, number> = {};
  for (const list of Object.values(siblings)) {
    const sorted = [...list].sort((a, b) => a.c[6] - b.c[6] || a.c[7] - b.c[7]);
    sorted.forEach((it, k) => (slotOf[it.key] = sorted.length === 1 ? 0.5 : 0.3 + (0.4 * k) / (sorted.length - 1)));
  }
  const cardBoxes: Box[] = cards.map((p) => ({ x: p.x, y: p.y, w: CARD_W, h: CARD_H }));
  const placed: Box[] = [];
  const out: Record<string, LabelOut> = {};
  const queue = [...items].sort((a, b) => Number(b.keep) - Number(a.keep) || a.order - b.order);
  for (const it of queue) {
    const spots = tries(slotOf[it.key]).map((t) => {
      const p = curveAt(it.c, t);
      return { x: p.x, y: p.y + 4, box: labelBox(it.text, p.x, p.y + 4) };
    });
    const free = spots.filter((s) => !placed.some((b) => hit(b, s.box)));
    const best = free.find((s) => !cardBoxes.some((b) => hit(b, s.box))) || free[0];
    if (!best) continue;
    placed.push(best.box);
    out[it.key] = best;
  }
  return out;
}
