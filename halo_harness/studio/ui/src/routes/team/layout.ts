// The Team board laid out in code (3.0.8.0 R2; no layout library). Members
// are COLUMNS, one labelled box each (name, lineup and role, the harness
// chip). Stages are BOXES, one row each in the file's order (a stage_done
// trigger always names an earlier stage, so the DAG reads top to bottom),
// placed in the column of their lead and spanning the columns of all their
// members; an Orchestra or flow stage (no members of its own) spans the whole
// team. Blocks sit in a band under the columns as document / folder / git
// nodes. Edges: `stage_done:` triggers run down the right-hand gutter from
// stage to stage (the DAG), reads (dashed) and writes (solid) join a stage's
// bottom to a block's top, a `block_change:` trigger joins a block to the
// stage it starts. Pure: Board.tsx draws what this returns.
import type { StageSpec, TeamDoc } from "./types";

const MARGIN = 12;
const COL_W = 232;
const COL_GAP = 14;
export const HEAD = 72;
const STAGE_H = 60;
const STAGE_GAP = 16;
const INSET = 10;
const BAND_GAP = 40;
const BLOCK_W = 186;
const BLOCK_H = 58;
const BLOCK_GAP = 18;
const GUTTER = 30;
const LANE = 14;

export type Rect = { x: number; y: number; w: number; h: number };
export type Column = Rect & { member: string; index: number };
export type StageBox = Rect & { id: string; spec: StageSpec; cols: number[] };
export type BlockBox = Rect & { id: string };
export type EdgeKind = "done" | "reads" | "writes" | "change";
export type Edge = { key: string; kind: EdgeKind; from: string; to: string; d: string; mx: number; my: number };
export type Band = Rect;
export type Geometry = { width: number; height: number; columns: Column[]; stages: StageBox[]; blocks: BlockBox[]; edges: Edge[]; band: Band; colsBottom: number };

/** The member columns a stage sits in (an agent stage with no listed member runs the first one). */
export function stageCols(team: TeamDoc, s: StageSpec, rowMembers?: string[]): number[] {
  const names = rowMembers?.length ? rowMembers : s.members;
  const idx = (n: string) => team.members.findIndex((m) => m.name === n);
  let cols = names.map(idx).filter((i) => i >= 0);
  if (!cols.length && s.kind === "agent" && team.members.length) cols = [0];
  return cols;
}

/** A trigger's parts: ["manual"], ["stage_done", "draft"], ["block_change", "notes"]. */
export function parseTrigger(t: string): [string, string] {
  const i = (t || "manual").indexOf(":");
  return i < 0 ? [t || "manual", ""] : [t.slice(0, i), t.slice(i + 1)];
}

export function layout(team: TeamDoc, members: Record<string, string[]> = {}): Geometry {
  const n = Math.max(1, team.members.length);
  const colX = (i: number) => MARGIN + i * (COL_W + COL_GAP);
  const stages: StageBox[] = [];
  let y = MARGIN + HEAD + 12;
  for (const s of team.workflow.stages) {
    const cols = stageCols(team, s, members[s.id]);
    const lo = cols.length ? Math.min(...cols) : 0;
    const hi = cols.length ? Math.max(...cols) : n - 1;
    const x = colX(lo) + INSET;
    stages.push({ id: s.id, spec: s, cols, x, y, w: colX(hi) + COL_W - INSET - x, h: STAGE_H });
    y += STAGE_H + STAGE_GAP;
  }
  const colsBottom = Math.max(y - STAGE_GAP + 14, MARGIN + HEAD + 70);
  const columns: Column[] = team.members.map((m, i) => ({ member: m.name, index: i, x: colX(i), y: MARGIN, w: COL_W, h: colsBottom - MARGIN }));
  const inner = n * COL_W + (n - 1) * COL_GAP;
  const perRow = Math.max(1, Math.floor((inner + BLOCK_GAP) / (BLOCK_W + BLOCK_GAP)));
  const bandY = colsBottom + BAND_GAP;
  const blocks: BlockBox[] = team.blocks.map((b, i) => {
    const row = Math.floor(i / perRow), col = i % perRow;
    const inRow = Math.min(perRow, team.blocks.length - row * perRow);
    const used = inRow * BLOCK_W + (inRow - 1) * BLOCK_GAP;
    return { id: b.id, x: MARGIN + (inner - used) / 2 + col * (BLOCK_W + BLOCK_GAP), y: bandY + row * (BLOCK_H + BLOCK_GAP), w: BLOCK_W, h: BLOCK_H };
  });
  const rowsOfBlocks = Math.max(1, Math.ceil(team.blocks.length / perRow));
  const bandBottom = bandY + rowsOfBlocks * (BLOCK_H + BLOCK_GAP) - BLOCK_GAP;
  const band: Band = { x: MARGIN - 4, y: bandY - 26, w: inner + 8, h: bandBottom - bandY + 34 };
  const edges = edgesOf(stages, blocks, MARGIN + inner);
  const lanes = edges.filter((e) => e.kind === "done").length;
  return { width: MARGIN * 2 + inner + (lanes ? GUTTER + lanes * LANE : 0), height: bandBottom + MARGIN + 4, columns, stages, blocks, edges, band, colsBottom };
}

function edgesOf(stages: StageBox[], blocks: BlockBox[], right: number): Edge[] {
  const out: Edge[] = [];
  const st = new Map(stages.map((s) => [s.id, s]));
  const bl = new Map(blocks.map((b) => [b.id, b]));
  let lane = 0;
  for (const s of stages) {
    const [kind, ref] = parseTrigger(s.spec.trigger);
    if (kind === "stage_done" && st.has(ref)) {
      const a = st.get(ref)!, gx = right + GUTTER - 6 + lane * LANE, r = 8;
      const x1 = a.x + a.w, y1 = a.y + a.h / 2 - 8, x2 = s.x + s.w, y2 = s.y + s.h / 2 - 8;
      out.push({ key: `done:${ref}>${s.id}`, kind: "done", from: ref, to: s.id, mx: gx, my: (y1 + y2) / 2,
                 d: `M${x1} ${y1} H${gx - r} Q${gx} ${y1} ${gx} ${y1 + r} V${y2 - r} Q${gx} ${y2} ${gx - r} ${y2} H${x2 + 2}` });
      lane += 1;
    }
    if (kind === "block_change" && bl.has(ref)) {
      const b = bl.get(ref)!;
      out.push(curve(`change:${ref}>${s.id}`, "change", ref, s.id, b.x + b.w - 26, b.y, s.x + s.w - 30, s.y + s.h));
    }
  }
  for (const s of stages) {
    const touched = [...new Set([...s.spec.reads, ...s.spec.writes])].filter((id) => bl.has(id));
    touched.forEach((id, i) => {
      const b = bl.get(id)!;
      const sx = s.x + (s.w * (i + 1)) / (touched.length + 1);
      const both = s.spec.reads.includes(id) && s.spec.writes.includes(id);
      if (s.spec.reads.includes(id)) out.push(curve(`reads:${s.id}>${id}`, "reads", s.id, id, sx - (both ? 5 : 0), s.y + s.h, b.x + b.w / 2 - (both ? 5 : 0), b.y));
      if (s.spec.writes.includes(id)) out.push(curve(`writes:${s.id}>${id}`, "writes", s.id, id, sx + (both ? 5 : 0), s.y + s.h, b.x + b.w / 2 + (both ? 5 : 0), b.y));
    });
  }
  return out;
}

function curve(key: string, kind: EdgeKind, from: string, to: string, x1: number, y1: number, x2: number, y2: number): Edge {
  const down = y2 > y1;
  const k = Math.max(30, Math.abs(y2 - y1) / 2);
  const c1 = down ? y1 + k : y1 - k, c2 = down ? y2 - k : y2 + k;
  return { key, kind, from, to, mx: (x1 + x2) / 2, my: (y1 + y2) / 2, d: `M${x1} ${y1} C${x1} ${c1} ${x2} ${c2} ${x2} ${y2}` };
}
