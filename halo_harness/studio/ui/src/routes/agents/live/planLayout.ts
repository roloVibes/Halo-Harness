// The plan under Live, laid out (3.3.18.0 "The living canvas" part 2): main's block on the left, the lineup's other
// blocks -- each tier, each square -- in one column to its right, then "not in the plan" and any Orchestra run. Main's
// line into each tier or square block runs from main's title bar to one vertical bus, then straight into the block's
// title bar, its when label on that last stretch (one line per block, never crossing a box). Inside a block its agents sit
// in a grid of the Live node's own size (two to a row from 2 agents, three from 5, four from 10), so nothing inside is
// squished. A block nobody uses is its title bar alone (its name and its purpose). Pure.
import { DENSITY, type Density, type LiveBox } from "../../roles/liveLayout";
import type { LiveNode } from "../../roles/liveModel";
import type { Placement, PlanBlockDef } from "./planModel";
import { FAR_SCALE } from "./levels";

export const P_MARGIN = 28;
export const P_PAD = 12;
export const P_GAP = 16; // between two rows of a block's grid
export const HEAD_USED = 72; // the title, the counts, the purpose
export const HEAD_IDLE = 54; // the title, the purpose
export const BLOCK_MIN_W = 320;
export const LABEL_W = 176;
const FAR_W = 210; // a far block's width before FAR_SCALE: its name, counts and purpose, cut by an ellipsis
const BUS = 28; // from main's block to the bus
const LEG = BUS + LABEL_W + 24; // from main's block to the column of blocks
const COL_GAP = 24;

export type PlanBox = { def: PlanBlockDef; x: number; y: number; w: number; h: number; head: number; members: LiveNode[]; used: boolean };
export type PlanLine = { to: string; d: string; lx: number; ly: number; label: string };
export type PlanGeometry = { width: number; height: number; boxes: LiveBox[]; blocks: PlanBox[]; lines: PlanLine[]; far?: boolean };

export function colsFor(n: number, density: Density): number {
  const max = density === "compact" ? 5 : 4;
  return Math.min(max, n <= 1 ? 1 : n <= 4 ? 2 : n <= 9 ? 3 : 4);
}

export function planLayout(nodes: LiveNode[], defs: PlanBlockDef[], place: Placement, density: Density = "spread", rowH = 0, far = false): PlanGeometry {
  const S = far ? FAR_SCALE : 1; // part 4: far draws blocks only, FAR_SCALE larger (levels.ts)
  const base = DENSITY[density] || DENSITY.spread;
  const dims = { ...base, h: base.h + rowH }; // the "waits on" row
  const members = new Map<string, LiveNode[]>();
  for (const n of nodes) {
    const b = place.block.get(n.id) || "main";
    members.set(b, [...(members.get(b) || []), n]);
  }
  const all = [...defs];
  for (const id of members.keys()) if (!all.some((d) => d.id === id))
    all.push(id === "none" ? { id, kind: "none", title: "not in the plan", purpose: "agents no card of the lineup matches", when: "" }
      : { id, kind: "run", title: `goal run: ${(members.get(id) || []).find((n) => n.run && !n.lane)?.task || id.slice(4)}`.slice(0, 80), purpose: `run ${id.slice(4)}`, when: "" }); // 3.4.0.0 D: titled by its goal
  const boxes: LiveBox[] = [], blocks: PlanBox[] = [], lines: PlanLine[] = [];
  const size = (def: PlanBlockDef) => {
    const ms = members.get(def.id) || [];
    const cols = colsFor(ms.length, density), rows = Math.ceil(ms.length / cols);
    const head = (ms.length ? HEAD_USED : HEAD_IDLE) * S;
    const w = far ? FAR_W * S : Math.max(BLOCK_MIN_W, cols * dims.w + (cols - 1) * dims.hg + 2 * P_PAD);
    const h = head + (ms.length && !far ? P_PAD + rows * dims.h + (rows - 1) * P_GAP + P_PAD : 0);
    return { ms, cols, head, w, h };
  };
  const put = (def: PlanBlockDef, x: number, y: number) => {
    const s = size(def);
    blocks.push({ def, x, y, w: s.w, h: s.h, head: s.head, members: s.ms, used: s.ms.length > 0 });
    if (!far) s.ms.forEach((n, i) => {
      const r = Math.floor(i / s.cols), c = i % s.cols;
      const inRow = Math.min(s.cols, s.ms.length - r * s.cols);
      const rowW = inRow * dims.w + (inRow - 1) * dims.hg;
      boxes.push({ node: n, x: x + (s.w - rowW) / 2 + c * (dims.w + dims.hg), y: y + s.head + P_PAD + r * (dims.h + P_GAP), w: dims.w, h: dims.h, depth: 1, from: null, d: "" });
    });
    return s;
  };
  const mainDef = all.find((d) => d.id === "main") || { id: "main", kind: "main" as const, title: "main", purpose: "", when: "" };
  const m = put(mainDef, P_MARGIN, P_MARGIN);
  const sx = P_MARGIN + m.w, sy = P_MARGIN + m.head / 2; // from main's title bar: never across a box inside main's block
  const colX = P_MARGIN + m.w + LEG * S, busX = P_MARGIN + m.w + BUS * S;
  let y = P_MARGIN, colW = 0;
  for (const def of all) {
    if (def.id === "main") continue;
    const s = put(def, colX, y);
    if (def.kind === "tier" || def.kind === "square") {
      const ty = y + s.head / 2;
      lines.push({ to: def.id, d: `M${sx} ${sy} H${busX} V${ty} H${colX}`, lx: busX + 10 * S, ly: ty - 20 * S, label: def.when });
    }
    colW = Math.max(colW, s.w);
    y += s.h + COL_GAP; // far too: blocks only, the column stays short
  }
  const width = colX + colW + P_MARGIN, height = Math.max(P_MARGIN + m.h, y - COL_GAP) + P_MARGIN;
  return { width: Math.max(320, width), height: Math.max(200, height), boxes, blocks, lines, far };
}
