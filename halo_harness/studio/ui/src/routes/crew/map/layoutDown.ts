// Session's drawing of the run, top to bottom (3.6.0.2 R6, R7, R8, R14's place, R45). Pure: width in, boxes and lines out;
// no React, no DOM, no store, no clock. The ranks are Agents' columns (`columns()` of layout.ts: main 0, a box one more
// than its deepest source); Agents -> Map keeps `layout()`, untouched.
// - Main alone on row 0 over the spine; a rank wraps two 184 px boxes a row (one when the drawer is under 400 px), a new
//   rank starts a row, an odd last box sits left. A saved workflow on no box of the map is a full-width row under its
//   caller (the last row of the caller's rank + 1); a box of the map with a block keeps its place.
// - A line leaves its box's bottom centre and enters its target's top; it turns only in the bands between rows and runs
//   down the spine (the 16 px between the two columns) past the rows it skips, or down the outer pad past a full-width row.
//   Several lines into one box enter 14 px apart about its centre. A band is as tall as its lanes need.
// - The boxes no line from main reaches wait below the last rank (reach.ts); P3 draws truth.ts's heading at `band.y`.
import { columns } from "./layout";
import type { DrawBox, DrawLine } from "./mapTypes";
import { split } from "./reach";

export const DOWN = { BOX_W: 184, BOX_H: 56, LINE_H: 18, SPINE: 16, PAD: 12, PAD_TIGHT: 8, RANK_BAND: 28, ROW_BAND: 16, LANE: 8,
                      STEP: 14, BAND_HEAD: 36 } as const;

export type PlacedDown = DrawBox & { x: number; y: number; w: number; h: number; rank: number; row: number; unreached?: boolean };
export type RoutedDown = DrawLine & { key: string; d: string; entry: number };
export type DownView = { boxes: DrawBox[]; strip: DrawBox[]; lines: DrawLine[] };
export type DownBand = { y: number; head: number; ids: string[] };
export type Down = { boxes: PlacedDown[]; lines: RoutedDown[]; w: number; h: number; per: 1 | 2; pad: number; band: DownBand | null };

/** Two boxes a row when the drawer's clientWidth holds them (>= 400), else one. */
export const perRow = (clientWidth: number): 1 | 2 => (clientWidth >= 400 ? 2 : 1);
/** The side pad: 8 when 400 <= clientWidth < 408, else 12 (top and bottom stay 12). */
export const padFor = (clientWidth: number): number => (clientWidth >= 400 && clientWidth < 408 ? DOWN.PAD_TIGHT : DOWN.PAD);

/** A box's height before it is measured: 56 + 18 x (lines - 2); a name wraps every 22 characters, plus "kind · state";
 *  a block is its head plus one row per step, EVERY step. */
export function estimateDown(b: DrawBox): number {
  const lines = b.block ? 1 + b.block.steps.length : Math.max(1, Math.ceil(b.name.length / 22)) + 1;
  return Math.max(DOWN.BOX_H, DOWN.BOX_H + DOWN.LINE_H * (lines - 2));
}

type Row = { rank: number; boxes: DrawBox[]; full: boolean };
type Run = { key: string; from: string; a: number; b: number; lane: number };

export function layoutDown(v: DownView, height: (b: DrawBox) => number, clientWidth: number, opts: { bandHead?: number } = {}): Down {
  const { BOX_W, SPINE, PAD, LANE, STEP } = DOWN;
  const per = perRow(clientWidth), pad = padFor(clientWidth);
  const w = 2 * pad + per * BOX_W + SPINE; // two a row: 408 (400 with pad 8); one a row: the spine right of the column, 224
  const spine = pad + BOX_W + SPINE / 2;
  const under = (b: DrawBox) => b.block?.under;
  const links = [...v.lines, ...[...v.boxes, ...v.strip].filter((b) => under(b)).map((b) => ({ from: under(b)!, to: b.id }))];
  const { reached, unreached } = split(v.boxes, v.strip, links);
  const col = columns(reached.filter((b) => !under(b)), v.lines);
  const rankOf = (b: DrawBox): number | undefined => (under(b) ? (col.has(under(b)!) ? col.get(under(b)!)! + 1 : undefined) : col.get(b.id));
  const left = [...unreached, ...reached.filter((b) => rankOf(b) === undefined)];
  const onMap = reached.filter((b) => rankOf(b) !== undefined);

  // Rows: rank by rank; inside a rank by the earliest-placed box that feeds it, then input order; blocks last, full width.
  const rows: Row[] = [];
  const order = new Map<string, number>();
  const ranks = Math.max(0, ...onMap.map((b) => rankOf(b)!));
  for (let r = 0; r <= ranks; r++) {
    const here = onMap.filter((b) => rankOf(b) === r);
    const key = (b: DrawBox) => Math.min(Infinity, ...v.lines.filter((l) => l.to === b.id && order.has(l.from)).map((l) => order.get(l.from)!));
    const plain = here.filter((b) => !under(b)).map((b, i) => ({ b, i, k: key(b) })).sort((p, q) => p.k - q.k || p.i - q.i).map((p) => p.b);
    for (let i = 0; i < plain.length; i += per) rows.push({ rank: r, boxes: plain.slice(i, i + per), full: false });
    for (const b of here.filter((x) => under(x))) rows.push({ rank: r, boxes: [b], full: true });
    for (const b of [...plain, ...here.filter((x) => under(x))]) order.set(b.id, order.size);
  }

  // x is fixed by the width; so are the lines' runs, hence the bands' lanes, before any y.
  const placed = new Map<string, PlacedDown>();
  const rowH: number[] = [];
  rows.forEach((row, ri) => {
    row.boxes.forEach((b, i) => {
      const x = row.full ? pad : row.rank === 0 && per === 2 ? (w - BOX_W) / 2 : pad + i * (BOX_W + SPINE);
      placed.set(b.id, { ...b, x, y: 0, w: row.full ? w - 2 * pad : BOX_W, h: Math.max(DOWN.BOX_H, height(b)), rank: row.rank, row: ri });
    });
    rowH.push(Math.max(...row.boxes.map((b) => placed.get(b.id)!.h)));
  });
  const cx = (p: PlacedDown) => p.x + p.w / 2;
  const drawn = v.lines.filter((l) => placed.has(l.from) && placed.has(l.to) && placed.get(l.to)!.row > placed.get(l.from)!.row);
  const entry = new Map<DrawLine, number>();
  for (const t of placed.values()) {
    const into = drawn.filter((l) => l.to === t.id)
      .sort((p, q) => cx(placed.get(p.from)!) - cx(placed.get(q.from)!) || (p.from < q.from ? -1 : p.from > q.from ? 1 : 0));
    const step = into.length > 1 ? Math.min(STEP, (t.w - 16) / (into.length - 1)) : 0;
    into.forEach((l, k) => entry.set(l, cx(t) + (k - (into.length - 1) / 2) * step));
  }
  const bands: Run[][] = rows.map(() => []);
  const plan = drawn.map((l) => {
    const s = placed.get(l.from)!, t = placed.get(l.to)!, ex = cx(s), en = entry.get(l)!, key = `${l.from}>${l.to}`;
    const runs: [number, Run][] = [];
    if (t.row === s.row + 1) runs.push([s.row, { key, from: l.from, a: ex, b: en, lane: 0 }]);
    else {
      const blocked = rows.some((r, i) => r.full && i > s.row && i < t.row);
      const trunk = !blocked ? spine : ex <= w / 2 ? pad / 2 : w - pad / 2;
      runs.push([s.row, { key, from: l.from, a: ex, b: trunk, lane: 0 }], [t.row - 1, { key, from: l.from, a: trunk, b: en, lane: 0 }]);
    }
    for (const [bi, run] of runs) if (run.a !== run.b) bands[bi].push(run);
    return { l, s, t, ex, en, runs };
  });

  // Lanes: a band's runs packed greedily (by left end, then key); runs whose spans overlap never share a lane, except runs
  // of one source from one point (a trunk that splits). Lanes 8 px apart, centred in the band.
  const lanes = bands.map((runs) => {
    const lo = (r: Run) => Math.min(r.a, r.b), hi = (r: Run) => Math.max(r.a, r.b);
    const packed: Run[][] = [];
    for (const r of [...runs].sort((p, q) => lo(p) - lo(q) || (p.key < q.key ? -1 : p.key > q.key ? 1 : 0))) {
      const fits = (lane: Run[]) => lane.every((o) => Math.max(lo(o), lo(r)) >= Math.min(hi(o), hi(r)) || (o.from === r.from && o.a === r.a));
      let i = packed.findIndex(fits);
      if (i < 0) i = packed.push([]) - 1;
      packed[i].push(r);
      r.lane = i;
    }
    return packed.length;
  });
  const bandH = rows.map((row, i) => (i + 1 < rows.length && rows[i + 1].rank !== row.rank
    ? Math.max(DOWN.RANK_BAND, 12 + LANE * lanes[i]) : Math.max(DOWN.ROW_BAND, 8 + LANE * lanes[i])));
  const rowY: number[] = [];
  let y = PAD;
  rows.forEach((_, i) => {
    rowY.push(y);
    y += rowH[i] + (i + 1 < rows.length ? bandH[i] : 0);
  });
  for (const p of placed.values()) p.y = rowY[p.row];
  const laneY = (bi: number, lane: number) => rowY[bi] + rowH[bi] + bandH[bi] / 2 + (lane - (lanes[bi] - 1) / 2) * LANE;

  const lines: RoutedDown[] = plan.map(({ l, s, t, ex, en, runs }) => {
    const pts: [number, number][] = [[ex, s.y + s.h]];
    for (const [bi, r] of runs) if (r.a !== r.b) pts.push([r.a, laneY(bi, r.lane)], [r.b, laneY(bi, r.lane)]);
    pts.push([en, t.y]);
    let d = `M${pts[0][0]} ${pts[0][1]}`, last = "";
    for (let i = 1; i < pts.length; i++) {
      const [px, py] = pts[i - 1], [nx, ny] = pts[i];
      if (px === nx && py === ny) continue;
      const cmd = px === nx ? `V${ny}` : `H${nx}`;
      d = cmd[0] === last ? d.replace(/[HV][^HV]*$/, cmd) : `${d} ${cmd}`;
      last = cmd[0];
    }
    return { ...l, key: `${l.from}>${l.to}`, d, entry: en };
  });

  // Not connected yet: a rank band, the heading's room, then the boxes two a row (one under 400), 16 px apart.
  const bottom = rows.length ? rowY[rows.length - 1] + rowH[rows.length - 1] : 0;
  let band: DownBand | null = null, end = bottom;
  if (left.length) {
    band = { y: bottom + DOWN.RANK_BAND, head: opts.bandHead ?? DOWN.BAND_HEAD, ids: left.map((b) => b.id) };
    let by = band.y + band.head;
    for (let i = 0; i < left.length; i += per) {
      const chunk = left.slice(i, i + per).map((b, k) => ({ ...b, x: pad + k * (BOX_W + SPINE), y: by, w: BOX_W,
        h: Math.max(DOWN.BOX_H, height(b)), rank: -1, row: rows.length + i / per, unreached: true }));
      for (const p of chunk) placed.set(p.id, p);
      end = by + Math.max(...chunk.map((p) => p.h));
      by = end + DOWN.ROW_BAND;
    }
  }
  return { boxes: [...placed.values()], lines, w, h: end + PAD, per, pad, band };
}
