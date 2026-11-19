// Auto's own groups (3.6.0.5 B2 B3 B4 B11 B22; R14 R15 R17 as changed for Auto): which group every helper of a session on
// Auto is drawn in, from its agent rows alone. Every child of main is in exactly one group; a child of a child is a member
// of its parent's group; a lone child is a group of one that a later child with the same key joins in place (the group's
// n and key never change, so no box changes its container); every hand-off is main's pick, drawn into its group, never
// counted off the map. A group is named in ONE place, groupName (../live/groups.ts). Pure: no React, no DOM, no store,
// no clock (tests/test_map_groups.py runs it in node).
//
// Where a row goes and its group's n: placeGroups (../live/groups.ts; the Live tree and the Timeline number the same
// groups with it, b/batch07). A workflow run's group lists its steps (R14's rows) only when the step runner's
// frames gave the workflow a block (`blocks[W]`: only a crew workflow sends `map_step`); without one it is drawn by its
// members like any other group.
import type { AgentRow } from "../../fleet/types";
import { groupName, isMainRow, placeGroups } from "../live/groups";
import type { StepRow } from "./mapTypes";
import { stateOf, type BoxState, type OvRow } from "./overlay";
import { rowStep, type BlockLit } from "./overlayBlocks";

export type GRow = OvRow & { spawn?: AgentRow["spawn"]; since?: number | null; model_reason?: string | null; ended?: number | null };
export type Member = { aid: string; parent: string; who: string; description: string; model: string; state: BoxState; cost: number;
  reason: string; made: boolean; started: number; ended: number; by?: string; step?: number };
export type AutoGroup = { n: number; key: string; by: "workflow" | "task" | "reply"; name: string; workflow?: string; members: Member[];
  steps?: StepRow[]; first: number };

const str = (v: unknown): string => (v == null ? "" : String(v));
const num = (v: unknown): number => (typeof v === "number" && isFinite(v) ? v : 0);
const ANY = ["", "general-purpose"]; // the type the engine writes when the call named none (agent/subagent.py)

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
  const main = rows.find(isMainRow)?.agent_id || "main";
  const out: AutoGroup[] = [];
  for (const g of placeGroups(rows)) { // the one placing and numbering (../live/groups.ts), shared with the Live tree
    const members: Member[] = g.rows.map((r) => {
      const m: Member = { aid: r.agent_id, parent: str(r.parent), who: whoOf(r), description: str(r.spawn?.description) || str(r.task),
        model: str(r.model), state: stateOf([r]), cost: num(r.cost_usd), reason: str(r.model_reason),
        made: r.crew ? !!r.crew.made_up : ANY.includes(str(r.name)), started: num(r.since), ended: num(r.ended) };
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
