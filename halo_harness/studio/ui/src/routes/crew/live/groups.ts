// Live in groups (3.3.16.3, the owner: "I wish I could see better groupings of these sub-agents ... here's this one task
// and here's the sub-agents in there, and it points to that group"): which box each agent of the tree is drawn in. Pure;
// the words come from the agent rows (agent/agent_hooks.py `spawn_of`, workflows/receipts.py), never a model call.
//
//   square  a square's agent (its row's `square`) and every agent under it: titled by the square's name, its DOES line
//           under it, in the engine's lane colour
//   task    the children of one parent started by one step of it (one reply's Agent calls: `spawn.step`), MIN_TASK or
//           more: titled by the task (titleOf below); a square's agent among them is its own group inside this one.
//           3.6.0.5 B5: main's children whose rows carry `spawn.group` are grouped by its key instead (crew/groups.py),
//           and every group of main's children is named by groupName, the one name Session, Live, the Timeline and
//           Glance give it
//   tier    an agent of an explicit lineup tier in no box above: the tier's faint group, titled by its purpose (else its
//           name) -- today's faint lineup-card group, which stays for a lineup with no tiers
//   alone   a single agent started alone is not boxed
//   run     3.4.0.0 D: a goal run's lanes, in a box under its lead, titled by the goal (routes/agents/live/runLanes.tsx)
//
// Groups nest one level (a square inside a task); deeper, the agents are drawn as a tree inside the outer box. When the
// agents of a group were picked by Auto, the second line says the pick in plain words (whyOf).
import type { WorkRecord } from "../../../lib/work/record";
import { shortModel } from "../../../lib/modelName";
import type { LiveNode } from "./liveModel";
import type { Tier } from "../models/types";
import type { AgentRow } from "../../fleet/types";

export const MIN_TASK = 2;
export type GroupKind = "task" | "square" | "tier" | "run"; // 3.4.0.0 D: a goal run's lanes under its lead (runLanes.tsx)
/** On each node: the box it is drawn in -- `parent` the node the box hangs under, `outer` the box around this one. */
export type GroupTag = { id: string; title: string; why: string; kind: GroupKind; engine?: string; parent: string | null; outer?: string };

const NTH = /\s*\(\d+\/\d+\)\s*$/; // a count job's "(2/3)"
const OPENERS = /^(ok(ay)?[,.]?\s+)?(now\s+)?(i'll|i will|let me|let's|i'm going to|i am going to)\s+/i;

const clause = (s: string): string => s.split(/(?<=[.;!?:])\s|\s--\s/)[0].replace(/[.;:!?]+$/, "").trim();
const cap = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : s);

/** The task in a few words: one description they all share, else the parent's own line before the calls (its first
 *  clause), else the words the descriptions start with (two or more), else the first description "and N more". */
export function titleOf(descs: string[], lead: string): string {
  const d = descs.map((x) => x.replace(NTH, "").trim()).filter(Boolean);
  if (d.length === descs.length && d.length && d.every((x) => x === d[0])) return d[0];
  const said = clause(lead || "").replace(OPENERS, "");
  if (said.split(/\s+/).length >= 2) return cap(said);
  const words = d.map((x) => x.split(/\s+/));
  let n = 0;
  while (words.length && words.every((w) => w[n] !== undefined && w[n].toLowerCase() === words[0][n].toLowerCase())) n += 1;
  if (n >= 2) return words[0].slice(0, n).join(" ");
  return d.length ? (d.length > 1 ? `${d[0]} and ${d.length - 1} more` : d[0]) : `${descs.length} agents`;
}

/** Auto's pick in plain words: "3 readers on kimi-k3 for a pdf in the task, 1 reviewer on glm-5" ("" when no member
 *  carries a pick's reason). The "for" words are the deciding need, the reason's first clause, when one bucket shares it. */
export function whyOf(members: { role: string; name: string; model: string; reason: string }[]): string {
  const picked = members.filter((m) => m.reason);
  if (!picked.length) return "";
  const buckets = new Map<string, { who: string; model: string; n: number; why: Set<string> }>();
  for (const m of picked) {
    const who = m.role || m.name, model = shortModel(m.model);
    const k = `${who}|${model}`;
    const b = buckets.get(k) || { who, model, n: 0, why: new Set<string>() };
    b.n += 1;
    b.why.add(m.reason.split(",")[0].trim());
    buckets.set(k, b);
  }
  return [...buckets.values()].map((b) => {
    const who = b.n > 1 && !b.who.endsWith("s") ? `${b.who}s` : b.who;
    const why = b.why.size === 1 ? [...b.why][0] : "";
    return `${b.n} ${who}${b.model ? ` on ${b.model}` : ""}${why ? ` for ${why}` : ""}`;
  }).join(", ");
}

type Row = WorkRecord["agents"][number];
/** What groupName reads of a member's registry row. */
export type NameRow = { agent_id?: string; since?: number | null; spawn?: AgentRow["spawn"]; crew?: { workflow?: string } | null };

const since = (r: NameRow): number => (typeof r.since === "number" && isFinite(r.since) ? r.since : Infinity);

/** 3.6.0.5 B5: a group's one name. "workflow {W}" (its key `workflow:{W}#{run}`, the LAST "#" splits; rows with no group:
 *  the first-registered member's `crew.workflow`); else the task main gave the member registered first (smallest
 *  `since`, ties in input order), as written -- a later member's own words never name it; else titleOf over the
 *  members' descriptions and the first one's lead (when one is given and titleOf finds words); else "Task {n}". */
export function groupName(rows: NameRow[], n: number): string {
  const order = rows.map((r, i) => ({ r, i })).sort((p, q) => since(p.r) - since(q.r) || p.i - q.i).map((p) => p.r);
  const first = order[0];
  const keys = rows.map((r) => String(r.spawn?.group?.key || "")).filter(Boolean);
  const key = keys.find((k) => k.startsWith("workflow:"));
  if (key) {
    const cut = key.lastIndexOf("#");
    return `workflow ${key.slice("workflow:".length, cut >= "workflow:".length ? cut : key.length)}`;
  }
  if (!keys.length && first?.crew?.workflow) return `workflow ${first.crew.workflow}`;
  const task = String(first?.spawn?.task || "");
  if (task.trim()) return task;
  const descs = order.map((r) => String(r.spawn?.description || ""));
  const lead = String(first?.spawn?.lead || "");
  if (descs.some((d) => d.trim()) || lead.trim()) {
    const t = titleOf(descs, lead);
    if (t !== `${descs.length} agents`) return t;
  }
  return `Task ${n}`;
}

/** The nodes of one session's record, each with the box it is drawn in (`group`); `tiers`: the open lineup's. */
export function withGroups(nodes: LiveNode[], rec: WorkRecord, tiers: Tier[] = []): LiveNode[] {
  const row = new Map<string, Row>(rec.agents.map((a) => [a.id, a]));
  const kids = new Map<string, LiveNode[]>();
  for (const n of nodes) if (n.parent) kids.set(n.parent, [...(kids.get(n.parent) || []), n]);
  const tag = new Map<string, GroupTag>();
  const depth = new Map<string, number>(); // how many boxes a node is inside
  const put = (id: string, g: GroupTag, d: number) => {
    const walk = (x: string, seen = new Set<string>()) => {
      if (seen.has(x)) return;
      seen.add(x);
      if (!tag.has(x) || (depth.get(x) || 0) < d) {
        tag.set(x, g);
        depth.set(x, d);
      }
      for (const k of kids.get(x) || []) walk(k.id, seen);
    };
    walk(id);
  };
  // in tree order (parents before their children), so an outer box is known before the boxes inside it
  for (const n of nodes) {
    const sq = row.get(n.id)?.row.square;
    if (sq?.name) {
      const outer = tag.get(n.id), d = (depth.get(n.id) || 0) + 1;
      if (d <= 2) put(n.id, { id: `q:${rec.id}|${n.id}`, kind: "square", parent: n.parent, outer: outer?.id, title: `square ${sq.name}`,
                              why: String(sq.does || ""), engine: sq.engine || "session" }, d);
    }
    const list = (kids.get(n.id) || []).filter((k) => !k.virtual);
    const steps = new Map<string, LiveNode[]>();
    const isMain = !n.parent; // B5: main's children group by their `spawn.group` key when their rows carry one
    for (const k of list) {
      const spawn = row.get(k.id)?.row.spawn;
      const st = (isMain && spawn?.group?.key) || spawn?.step;
      if (st) steps.set(st, [...(steps.get(st) || []), k]);
    }
    const rank = [...steps.keys()]; // a group with no engine n: its rank in start order
    const startOf = (ms: LiveNode[]) => Math.min(...ms.map((m) => since(row.get(m.id)?.row || {})));
    rank.sort((a, b) => startOf(steps.get(a)!) - startOf(steps.get(b)!));
    for (const [st, members] of steps) {
      if (members.length < MIN_TASK) continue;
      const outer = tag.get(n.id), d = (depth.get(n.id) || 0) + 1;
      if (d > 2) continue; // deeper than one level of nesting: a tree inside the outer box
      const spawns = members.map((m) => row.get(m.id)?.row.spawn);
      const gn = Number(spawns.find((s) => s?.group?.n)?.group?.n) || rank.indexOf(st) + 1;
      const g: GroupTag = { id: `t:${rec.id}|${st}`, kind: "task", parent: n.id, outer: outer?.id,
        title: isMain ? groupName(members.map((m) => row.get(m.id)?.row || {}), gn)
          : titleOf(spawns.map((s) => String(s?.description || "")), String(spawns[0]?.lead || "")),
        why: whyOf(members.map((m) => ({ role: m.role, name: m.name, model: m.model, reason: row.get(m.id)?.reason || "" }))) };
      for (const m of members) put(m.id, g, d);
    }
  }
  const tierOf = new Map<string, Tier>();
  for (const t of tiers) if (!t.implicit) for (const id of t.node_ids || []) tierOf.set(id, t);
  return nodes.map((n) => {
    const g = tag.get(n.id);
    if (g) return { ...n, group: g };
    const t = n.card ? tierOf.get(n.card) : undefined;
    return t ? { ...n, group: { id: `tier:${t.name}`, kind: "tier", parent: null, title: t.purpose || `tier ${t.name}`, why: "" } } : n;
  });
}
