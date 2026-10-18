// The layered layout the plan canvas and the flow graph share (3.0.9.0 R2):
// one column box per DAG layer, left to right (layer 0 = "at once"), the
// cards stacked in each box in their list order, every box as tall as the
// tallest; an optional empty box after the last one is the drop target for
// "a new layer". Edges run from a card's right edge to the next card's left.
export const CARD_W = 224;
export const CARD_H = 104;
export const GAP_X = 64;
export const GAP_Y = 12;
export const HEAD = 38;
export const PAD = 14;
export const BOX_PAD = 12;

export type Pos = { x: number; y: number };
export type Box = { x: number; y: number; w: number; h: number };
export type Laid = { pos: Record<string, Pos>; boxes: Box[]; columns: string[][]; w: number; h: number };

/** `{id: layer}`: 0 without upstreams, else one below the deepest upstream (a cycle counts as 0). */
export function layersOf(ids: string[], deps: Record<string, string[]>): Record<string, number> {
  const memo: Record<string, number> = {};
  const known = new Set(ids);
  const depth = (id: string, path: string[]): number => {
    if (id in memo) return memo[id];
    if (path.includes(id)) return 0;
    const ups = (deps[id] || []).filter((u) => known.has(u) && u !== id && !path.includes(u));
    const d = ups.length ? 1 + Math.max(...ups.map((u) => depth(u, [...path, id]))) : 0;
    memo[id] = d;
    return d;
  };
  for (const id of ids) depth(id, []);
  return memo;
}

export function layout(ids: string[], layer: Record<string, number>, extra: boolean, cardH = CARD_H): Laid {
  const n = ids.length ? Math.max(...ids.map((id) => layer[id] || 0)) + 1 : 1;
  const columns: string[][] = Array.from({ length: n + (extra ? 1 : 0) }, () => []);
  for (const id of ids) columns[layer[id] || 0].push(id);
  const tallest = Math.max(1, ...columns.map((c) => c.length));
  const boxH = HEAD + tallest * (cardH + GAP_Y) - GAP_Y + BOX_PAD;
  const boxW = CARD_W + 2 * BOX_PAD;
  const boxes = columns.map((_c, k) => ({ x: PAD + k * (boxW + GAP_X), y: PAD, w: boxW, h: boxH }));
  const pos: Record<string, Pos> = {};
  columns.forEach((col, k) => col.forEach((id, i) => (pos[id] = { x: boxes[k].x + BOX_PAD, y: boxes[k].y + HEAD + i * (cardH + GAP_Y) })));
  const last = boxes[boxes.length - 1];
  return { pos, boxes, columns, w: last.x + last.w + PAD, h: boxH + 2 * PAD };
}

/** The box index under world x (null between boxes or past the last). */
export function boxAt(boxes: Box[], x: number, y: number): number | null {
  const i = boxes.findIndex((b) => x >= b.x - GAP_X / 2 && x <= b.x + b.w + GAP_X / 2 && y >= b.y - 40 && y <= b.y + b.h + 80);
  return i < 0 ? null : i;
}

/** An edge from card a's right edge to card b's left edge, and its midpoint. */
export function edgePath(a: Pos, b: Pos, cardH = CARD_H): { d: string; mx: number; my: number } {
  const x1 = a.x + CARD_W, y1 = a.y + cardH / 2, x2 = b.x, y2 = b.y + cardH / 2;
  const bend = Math.max(36, Math.abs(x2 - x1) / 2);
  const back = x2 <= x1; // an upstream drawn in the same or a later column (a cycle being fixed)
  const c1 = back ? x1 + 40 : x1 + bend, c2 = back ? x2 - 40 : x2 - bend;
  return { d: `M${x1},${y1} C${c1},${y1} ${c2},${y2} ${x2},${y2}`, mx: (x1 + x2) / 2, my: (y1 + y2) / 2 };
}
