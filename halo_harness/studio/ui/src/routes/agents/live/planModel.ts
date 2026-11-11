// The plan under Live, as blocks (3.3.18.0 "The living canvas" part 2): the lineup's main, each tier, each enabled square
// -- the map, quiet and still -- and which block each live agent sits in. Pure.
//
//   main      the session's root agent (main), and the cards of main's own tier
//   square    a square's agent (its row's `square`) and every agent under it, in that square's block; a square the
//             lineup does not enable is not in the plan
//   tier      an agent the lineup's cards match (alias, bio, a role only one card has: roles/live.ts matchNode) sits in
//             its card's tier
//   inherits  an agent no card matches works in the block of the nearest agent above it that is in one (a tier member's
//             helpers stay in its tier); under main directly, it is "not in the plan", with why
//   run       an Orchestra run's lead and lanes: their own block (a run is not the lineup's)
import type { WorkRecord } from "../../../lib/work/record";
import { matchNode } from "../../roles/live";
import type { LiveNode } from "../../roles/liveModel";
import type { GraphEdge, LiveAgent } from "../../roles/types";
import type { Plan } from "./planStore";

export type BlockKind = "main" | "tier" | "square" | "none" | "run";
export type PlanBlockDef = { id: string; kind: BlockKind; title: string; purpose: string; when: string };
export const NONE_ID = "none";

const uniq = (xs: string[]) => [...new Set(xs.map((x) => x.trim()).filter(Boolean))];

/** main's words on its lines into the cards of one tier ("implement, fix · research"): the plan's when for that block. */
function tierWhen(edges: GraphEdge[], ids: string[], main: string): string {
  const words = uniq(edges.filter((e) => e.kind === "delegation" && e.from === main && ids.includes(e.to)).flatMap((e) => e.label.split(",")));
  return words.length ? `says ${words.slice(0, 4).join(", ")}${words.length > 4 ? " ..." : ""}` : "main delegates";
}

/** The plan's blocks in order: main, the tiers, the squares (the "not in the plan" box and runs are added when used). */
export function planBlocks(p: Plan): PlanBlockDef[] {
  const g = p.graph;
  if (!g) return [];
  const main = g.nodes.find((n) => n.role === "main")?.id || "";
  const name = (id: string) => { const n = g.nodes.find((x) => x.id === id); return n ? n.alias || n.role || n.agent : id; };
  const out: PlanBlockDef[] = [{ id: "main", kind: "main", title: "main", purpose: main ? `${name(main)}: takes your ask and hands work out` : "takes your ask", when: "" }];
  for (const t of g.tiers) {
    const ids = t.node_ids.filter((id) => id !== main);
    if (!ids.length && t.node_ids.includes(main)) continue; // main's own tier is the main block
    out.push({ id: `tier:${t.name}`, kind: "tier", title: t.purpose || `tier ${t.name}`, when: tierWhen(g.edges, ids, main),
               purpose: ids.length ? `${t.purpose ? `tier ${t.name}: ` : ""}${ids.map(name).join(", ")}` : `tier ${t.name}: no cards yet` });
  }
  for (const q of p.squares)
    out.push({ id: `square:${q.ref}`, kind: "square", title: `square ${q.ref}`, purpose: q.does || q.line || "", when: q.when_label || "covers " + (q.covers || []).join(", ") });
  return out;
}

type Row = WorkRecord["agents"][number];

function asLive(n: LiveNode, r: Row | undefined): LiveAgent {
  return { key: n.key, harness: "", session: "", session_id: "", agent_id: n.id, parent: n.parent, name: n.name, role: n.role, bio: r?.bio || "",
           lineup: r?.lineup || "", model: n.model, state: n.state, task: n.task, current: n.current, cost_usd: n.cost || 0, since: n.started || 0,
           activity: "", tool: "", calls: 0, control: "all" };
}

export type Placement = { block: Map<string, string>; why: Map<string, string> };

/** Which block each node sits in (and, for "not in the plan", why). Nodes come parents first. */
export function placeAgents(nodes: LiveNode[], rec: WorkRecord | null, p: Plan, blocks: PlanBlockDef[]): Placement {
  const block = new Map<string, string>(), why = new Map<string, string>();
  const ids = new Set(blocks.map((b) => b.id));
  const rows = new Map((rec?.agents || []).map((a) => [a.id, a]));
  const g = p.graph!;
  const main = g.nodes.find((n) => n.role === "main")?.id || "";
  const tierOf = new Map<string, string>();
  for (const t of g.tiers) for (const id of t.node_ids) tierOf.set(id, `tier:${t.name}`);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const none = (n: LiveNode, w: string) => (block.set(n.id, NONE_ID), why.set(n.id, w));
  for (const n of nodes) {
    if (n.run) { block.set(n.id, `run:${n.run}`); continue; }
    if (n.virtual) { none(n, "its parent is not in this session's frames"); continue; }
    if (!n.parent || !byId.has(n.parent)) { block.set(n.id, "main"); continue; }
    const up = block.get(n.parent) || "";
    if (n.square) {
      const id = `square:${n.square}`;
      if (ids.has(id)) block.set(n.id, id);
      else none(n, `square ${n.square} is not enabled on ${p.lineup}`);
      continue;
    }
    if (up.startsWith("square:")) { block.set(n.id, up); continue; } // a square's helpers work in its block
    const card = matchNode(asLive(n, rows.get(n.id)), g.nodes, p.lineup);
    const t = card ? (card.id === main ? "main" : tierOf.get(card.id) || "") : "";
    if (t && ids.has(t)) { block.set(n.id, t); continue; }
    if (up && up !== "main" && up !== NONE_ID) { block.set(n.id, up); continue; }
    const r = rows.get(n.id);
    none(n, `no card of ${p.lineup} matches its role (${n.role || "none"}) or its bio (${r?.bio || "none"})`);
  }
  return { block, why };
}

/** Part 4, far without a plan: the tree's own groups as the blocks (a task's, a square's, a tier's), main's block, and
 *  one block for the agents started alone. */
export function groupBlocks(nodes: LiveNode[]): { defs: PlanBlockDef[]; place: Placement } {
  const defs: PlanBlockDef[] = [{ id: "main", kind: "main", title: "main", purpose: "takes your ask and hands work out", when: "" }];
  const block = new Map<string, string>(), why = new Map<string, string>();
  for (const n of nodes) {
    if (!n.parent || n.kind || n.virtual) { block.set(n.id, n.run ? `run:${n.run}` : "main"); continue; }
    const g = n.group;
    const id = g ? g.id : "alone";
    if (!defs.some((d) => d.id === id))
      defs.push(g ? { id, kind: g.kind === "square" ? "square" : "tier", title: g.title, purpose: g.why || "", when: "" }
        : { id, kind: "tier", title: "started alone", purpose: "agents started one at a time", when: "" });
    block.set(n.id, id);
  }
  return { defs, place: { block, why } };
}
