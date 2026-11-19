// Auto's own groups (3.6.0.5 B2 B3 B4 B11 B22; R14 R15 R17 as changed for Auto): which group every helper of a session on
// Auto is drawn in, from its agent rows alone. Every child of main is in exactly one group; a child of a child is a member
// of its parent's group; a lone child is a group of one that a later child with the same key joins in place (the group's
// n and key never change, so no box changes its container); every hand-off is main's pick, drawn into its group, never
// counted off the map. A group is named in ONE place, groupName (../live/groups.ts). Pure: no React, no DOM, no store,
// no clock (tests/test_map_groups.py runs it in node).
//
// Where a row goes: its `spawn.group` (crew/groups.py); else (rows from before groups were written) the group of its
// ancestor whose parent is main: that row's `spawn.group`, else "workflow:{W}#" when it runs a step of W, else
// "reply:{spawn.step}", else "agent:{its id}". n: the engine's; a group with none takes, in order of its first start,
// the numbers after the largest engine n. A workflow run's group lists its steps (R14's rows) only when the step runner's
// frames gave the workflow a block (`blocks[W]`: only a crew workflow sends `map_step`); without one it is drawn by its
// members like any other group.
import type { AgentRow } from "../../fleet/types";
import { groupName } from "../live/groups";
import type { StepRow } from "./mapTypes";
import { stateOf, type BoxState, type OvRow } from "./overlay";
import { rowStep, type BlockLit } from "./overlayBlocks";

export type GRow = OvRow & { spawn?: AgentRow["spawn"]; since?: number | null; model_reason?: string | null };
export type Member = { aid: string; parent: string; who: string; description: string; model: string; state: BoxState; cost: number;
  reason: string; made: boolean; started: number; by?: string; step?: number };
export type AutoGroup = { n: number; key: string; by: "workflow" | "task" | "reply"; name: string; workflow?: string; members: Member[];
  steps?: StepRow[]; first: number };

const str = (v: unknown): string => (v == null ? "" : String(v));
const num = (v: unknown): number => (typeof v === "number" && isFinite(v) ? v : 0);
const at = (r: GRow): number => (typeof r.since === "number" && isFinite(r.since) ? r.since : Infinity);
const ANY = ["", "general-purpose"]; // the type the engine writes when the call named none (agent/subagent.py)
const isMain = (r: GRow): boolean => r.agent_id === "main" || (!r.parent && str(r.kind) === "main");
const DEPTH = 24;

/** The workflow W of a key "workflow:{W}#{run}" (the LAST "#" splits), else "". */
export function workflowOf(key: string): string {
  if (!key.startsWith("workflow:")) return "";
  const cut = key.lastIndexOf("#");
  return key.slice("workflow:".length, cut >= "workflow:".length ? cut : key.length);
}

function whoOf(r: GRow): string {
  if (r.crew?.saved && r.crew.agent) return str(r.crew.agent);
  const name = str(r.name), role = str(r.role);
  if (!ANY.includes(name)) return name;
  if (!ANY.includes(role)) return role;
  return "agent";
}

/** Auto's groups of one session's rows, in n order; `blocks`: the overlay's (blocksOf) for a workflow run's steps. */
export function autoGroups(rows: GRow[], blocks: Record<string, BlockLit> = {}): AutoGroup[] {
  const main = rows.find(isMain)?.agent_id || "main";
  const byId = new Map(rows.map((r) => [r.agent_id, r]));
  const top = (r: GRow): GRow => { // the ancestor whose parent is main (the row itself when the walk finds none)
    let x = r;
    for (let i = 0; i < DEPTH && str(x.parent) !== main; i++) {
      const up = byId.get(str(x.parent));
      if (!up || isMain(up)) break;
      x = up;
    }
    return str(x.parent) === main ? x : r;
  };
  const placeOf = (r: GRow): { key: string; n: number; by: AutoGroup["by"] } => {
    const own = r.spawn?.group;
    if (own?.key) return { key: own.key, n: num(own.n), by: own.by };
    const t = top(r), g = t.spawn?.group;
    if (g?.key) return { key: g.key, n: num(g.n), by: g.by };
    if (t.crew?.workflow) return { key: `workflow:${t.crew.workflow}#`, n: 0, by: "workflow" };
    if (t.spawn?.step) return { key: `reply:${t.spawn.step}`, n: 0, by: "reply" };
    return { key: `agent:${t.agent_id}`, n: 0, by: "reply" };
  };
  const order = rows.map((r, i) => ({ r, i })).filter((p) => !isMain(p.r)).sort((p, q) => at(p.r) - at(q.r) || p.i - q.i).map((p) => p.r);
  const found = new Map<string, { key: string; n: number; by: AutoGroup["by"]; rows: GRow[] }>();
  for (const r of order) {
    const p = placeOf(r);
    const g = found.get(p.key) || { ...p, rows: [] };
    if (!g.n && p.n) g.n = p.n;
    g.rows.push(r);
    found.set(p.key, g);
  }
  let next = Math.max(0, ...[...found.values()].map((g) => g.n));
  for (const g of found.values()) if (!g.n) g.n = ++next; // in order of first start: `order` is
  const out: AutoGroup[] = [];
  for (const g of found.values()) {
    const members: Member[] = g.rows.map((r) => {
      const m: Member = { aid: r.agent_id, parent: str(r.parent), who: whoOf(r), description: str(r.spawn?.description) || str(r.task),
        model: str(r.model), state: stateOf([r]), cost: num(r.cost_usd), reason: str(r.model_reason),
        made: r.crew ? !!r.crew.made_up : ANY.includes(str(r.name)), started: num(r.since) };
      if (str(r.parent) !== main) m.by = str(r.parent);
      if (typeof r.crew?.step === "number") m.step = r.crew.step;
      return m;
    });
    const w = workflowOf(g.key);
    const ag: AutoGroup = { n: g.n, key: g.key, by: g.by, name: groupName(g.rows, g.n), members, first: num(g.rows[0]?.since) };
    if (w) ag.workflow = w;
    const list = w ? blocks[w]?.steps || [] : [];
    if (list.length) {
      ag.steps = [...list].sort((p, q) => p.n - q.n).map((s) => {
        const mine = g.rows.filter((r) => str(r.crew?.workflow) === w && Number(r.crew?.step) === s.n);
        const r = mine[mine.length - 1]; // the newest round of that step
        return r ? { n: s.n, step: s.step, agent: str(r.crew?.agent) || str(r.name) || s.agent, model: str(r.model), state: rowStep(str(r.state)) }
          : { n: s.n, step: s.step, agent: s.agent, model: "", state: "next" as const };
      });
    }
    out.push(ag);
  }
  return out.sort((a, b) => a.n - b.n);
}
