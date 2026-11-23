// The map as drawn while it is lit (3.6.0.0 R4): the same drawing (view.ts), with what the running session adds --
// each helper it made up as a dashed box beside the box that started it (one column right, a dashed line from it, no
// When label: no line was drawn for it), and a Builder card it parked drawn as the builder's own ghosts. A session that
// did not start on a map draws on an empty map: main and its helpers, no invented lines.
// 3.6.0.0 R4b: one level only -- a helper a helper started is counted on it ("+N under it"), listed in the drawer.
import type { Change } from "../types";
import { firstLevel, type Overlay } from "./overlay";
import type { DrawBox, DrawLine, MapDetail, MapFile, StepRow } from "./mapTypes";
import type { MapView } from "./view";
import type { AutoGroup } from "./overlayGroups";

/** The file the lit map draws: the map itself, or (`bare`) main alone. */
export function litFile(file: MapFile | null, bare: boolean): MapFile | null {
  return file && bare ? { ...file, boxes: [], lines: [] } : file;
}

/** The builder's pending rows plus a session's parked card (every line of it drawn, as its card shows them all). */
export function withCard(pending: Change[], card: Change[]): Change[] {
  return card.length ? [...pending, ...card.map((c) => ({ ...c, ticked: true }))] : pending;
}

export const helperId = (aid: string) => `made-up:${aid}`;
export const flowId = (w: string) => `workflow:${w}`;

/** 3.6.0.2 R14 R15 R17, the drawing of a run (Session's Live drawer, Agents' Live view): no box per child -- a box carries
 *  its children as rows (the overlay's `kids`, drawn by RunRows.tsx); a workflow box of the map is its block, calm (every
 *  step "next", from the map's facts) until it runs; a workflow the session runs that is no box is a block on a full-width
 *  row under its caller, reached by a dashed line (off the map on a map of his when the hop that started it was). Steps'
 *  states are read from the overlay when drawn; here they only size the block. */
export function withRun(v: MapView, ov: Overlay | null, detail: MapDetail | null, plain: boolean): MapView {
  const models = new Map<string, string>();
  for (const f of Object.values(detail?.boxes || {})) for (const x of f.facts || []) if (x.model && !models.has(x.name)) models.set(x.name, x.model);
  const calm = (id: string): StepRow[] => (detail?.boxes[id]?.facts?.[0]?.steps || []).map((s, i) => {
    const agent = (s.agents || []).join(" + ");
    return { n: i + 1, step: s.name, agent, model: models.get(s.agents?.[0] || "") || "", state: "next" as const };
  });
  const blocks = ov?.blocks || {};
  const boxes: DrawBox[] = v.boxes.map((b) => {
    if (b.kind !== "workflow" || b.main) return b;
    const w = b.names[0] || b.name, lit = blocks[w];
    return { ...b, block: { workflow: w, steps: lit?.steps.length ? lit.steps : calm(b.id) } };
  });
  const lines: DrawLine[] = [...v.lines];
  const on = new Set(["main", ...v.boxes.map((b) => b.id)]);
  for (const [w, blk] of Object.entries(blocks)) {
    if (blk.box && on.has(blk.box)) continue;
    const under = on.has(blk.caller) ? blk.caller : "main";
    boxes.push({ id: flowId(w), kind: "workflow", name: w, names: [w], block: { workflow: w, steps: blk.steps, under } });
    lines.push({ from: under, to: flowId(w), helper: true, off: !plain && blk.off !== false });
  }
  return { ...v, boxes, lines };
}

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

/** 3.6.0.5 B8-B10: the drawing of a session on Auto -- main, then one block per group in n order (a new one after the
 *  last), each reached by one solid line from main; no strip. A group is placed by the existing layouts unedited: its
 *  `block.under` makes it layoutDown's full row under main (Session), and in layout.ts it is a box of column 1 (Agents ->
 *  Live); every drawing reads `group` before `block`. A map of his never comes here (withRun, as before). */
export const groupId = (n: number) => `group:${n}`;
export function autoView(v: MapView, groups: AutoGroup[]): MapView {
  const main = v.boxes.filter((b) => b.main);
  const from = main[0]?.id || "main";
  const boxes: DrawBox[] = [...main];
  const lines: DrawLine[] = [];
  for (const g of [...groups].sort((a, b) => a.n - b.n)) {
    const id = groupId(g.n), colour = ((((g.n - 1) % 4) + 4) % 4 + 1) as 1 | 2 | 3 | 4;
    boxes.push({ id, kind: "agent", name: g.name, names: [g.name], block: { workflow: "", steps: [], under: from },
                 group: { n: g.n, key: g.key, colour, members: g.members.map((m) => m.aid) } });
    lines.push({ from, to: id });
  }
  return { boxes, strip: [], lines };
}

/** B9 B10: a group's inside at a block `width` (border-box: a 2 px border and 10 px padding each side): members two a row
 *  when (inner - 8) / 2 is at least 160, else one a row at the inner width. L9b: three a row when (inner - 16) / 3 is at
 *  least 200, each rounded down to a whole px (three and two 8 px gaps never pass `inner`): only Auto's wide column. */
export function groupBox(width: number): { inner: number; per: 1 | 2 | 3; member: number } {
  const inner = width - 24, half = (inner - 8) / 2, third = (inner - 16) / 3;
  if (third >= 200) return { inner, per: 3, member: Math.floor(third) };
  return half >= 160 ? { inner, per: 2, member: half } : { inner, per: 1, member: inner };
}
