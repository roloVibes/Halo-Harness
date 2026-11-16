// Session's Live drawer at rest (3.6.0.2 R11, R12): pure arithmetic over the laid-out boxes (world px) and the zoom.
// - `viewHeight`: the scroll box is min(room, bottom of the last whole row + 12) tall, counted from the row at its top,
//   so no box is ever cut by its bottom edge; a box that does not fit waits wholly below it.
// - `belowCount`: the boxes wholly below the scroll box ("↓ {n} more below"); `nextTop`: one row down (the slot's press).
// - `firstSeen` / `keepSeen`: after a hand scroll, the first box he sees keeps its place when the drawing changes.
// No React, no DOM: node runs it (tests/test_studio_session_map_down.py).

export const PAD = 12; // the drawing's top and bottom pad (layoutDown's), and what is kept under the last whole row

export type Placed = { id: string; y: number; h: number };
export type RowBand = { top: number; bottom: number };

/** The rows of a drawing, top to bottom: boxes that share a top (within half a px) are one row. */
export function rowsOf(boxes: Placed[]): RowBand[] {
  const rows: RowBand[] = [];
  for (const b of [...boxes].sort((p, q) => p.y - q.y)) {
    const r = rows.find((x) => Math.abs(x.top - b.y) < 0.5);
    if (r) r.bottom = Math.max(r.bottom, b.y + b.h);
    else rows.push({ top: b.y, bottom: b.y + b.h });
  }
  return rows;
}

/** The scroll box's height (screen px) when it is scrolled to `top`: the bottom of the last row that is whole within
 *  `room`, plus the pad; the whole room when not even one row fits. */
export function viewHeight(rows: RowBand[], k: number, top: number, room: number): number {
  let best = 0;
  for (const r of rows) {
    if (r.bottom * k <= top + 0.5) continue; // above the view
    const end = (r.bottom + PAD) * k - top;
    if (end <= room + 0.5) best = Math.max(best, end);
  }
  return Math.max(0, Math.min(room, best || room));
}

/** How many boxes lie wholly below a scroll box `h` px tall scrolled to `top`. */
export function belowCount(boxes: Placed[], k: number, top: number, h: number): number {
  return boxes.filter((b) => b.y * k >= top + h - 0.5).length;
}

/** The scrollTop that brings the next row's top to the scroll box's top (one row down), or null at the last row. */
export function nextTop(rows: RowBand[], k: number, top: number): number | null {
  let cur = 0;
  rows.forEach((r, i) => { if (r.top * k <= top + PAD * k + 1) cur = i; });
  const next = rows[cur + 1];
  return next ? next.top * k : null;
}

/** The first box he sees at `top` (its bottom below the scroll box's top) and how far below the top it starts. */
export function firstSeen(boxes: Placed[], k: number, top: number): { id: string; off: number } | null {
  const seen = boxes.filter((b) => (b.y + b.h) * k > top + 0.5).sort((p, q) => p.y - q.y)[0];
  return seen ? { id: seen.id, off: seen.y * k - top } : null;
}

/** The scrollTop that puts the box `seen` where it was, in the new drawing (null when it is gone). */
export function keepSeen(boxes: Placed[], k: number, seen: { id: string; off: number }): number | null {
  const b = boxes.find((x) => x.id === seen.id);
  return b ? Math.max(0, b.y * k - seen.off) : null;
}
