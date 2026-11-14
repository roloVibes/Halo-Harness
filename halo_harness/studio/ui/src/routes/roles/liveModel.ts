// Roles Live's model (3.3.11.0 R2, the owner: "the roles tab kept up with what's happening during sessions"):
// the session's real agent tree, read through the work record adapter (lib/work/record.ts) and nothing else.
// One node per agent the record holds -- live, or finished and still in the frames -- and NOTHING dropped:
// an agent whose parent is not in the record hangs under one "unknown parent" node, said. The lineup card an
// agent matches (live.ts `matchNode`, the Plan canvas's glow rule) is informational here: the node keeps it
// (`card`) and the layout draws that card as a faint group behind its nodes. An `auto` pick carries its
// reason ("picked at spawn: coder on <model> -- <why>", the same words the TUI's `/agents live` prints). The
// glow is live.ts's (typing / a tool -> working, waiting on you, done, failed). Pure, plus the click / hop
// actions LiveMap.tsx and the J / K keys (routes/fleet/hop.ts) use.
import { recordRefs, sessionRecord, type RecordAgent, type WorkRecord } from "../../lib/work/record";
import { select } from "../fleet/actions";
import { activityOf } from "../fleet/frames";
import { allAgents, fleet, findAgent, type FleetState } from "../fleet/store";
import { pickLive } from "../agents/live/scope";
import { withGroups, type GroupTag } from "../agents/live/groups"; // 3.3.16.3: Live in groups
import { glowOf, type GlowState } from "./glow";
import { matchNode, openLiveTab, watchAgent } from "./live";
import { keyOf as cardKey, roles } from "./store";
import type { GraphNode, LiveAgent } from "./types";

export const UNKNOWN = "?unknown-parent";
const WORKING = ["queued", "running", "waiting", "paused"];

export type LiveNode = {
  id: string; key: string; parent: string | null; name: string; role: string; model: string; state: string; pick: string;
  activity: string; glow: GlowState | ""; card: string; cardLabel: string; task: string; current: string; cost: number | null;
  started: number | null; ended: number | null; virtual?: boolean;
  /** 3.4.1.1 (60): a replay's agent whose record gives its cost at its end only, drawn before it: "cost unknown". */
  costUnknown?: boolean;
  /** 3.3.16.0 R1: a live Orchestra run's node on the same tree (routes/agents/live/runLanes.tsx): its run, a lane's number
   *  and worktree (its branch). */
  run?: string; lane?: number; worktree?: string;
  /** 3.4.0.0 D: a lane's owns line on its box -- the claim ledger's keys it holds, else the units the plan gave it. */
  owns?: string[];
  /** 3.3.16.0 R2 (the fleet scope, routes/agents/live/fleetModel.ts): a machine, a session or a mission part on the same
   *  tree, and the harness and session every node of that scope belongs to. */
  kind?: "machine" | "session" | "part"; harness?: string; sid?: string;
  /** 3.3.16.0 R3: a square's agent or node (workflows/receipts.py): its name and its engine. */
  square?: string; engine?: string;
  /** 3.3.16.3 (routes/agents/live/groups.ts): the box it is drawn in -- a task, a square, a lineup tier. */
  group?: GroupTag;
};

/** "picked at spawn: <role> on <model> -- <reason>" for an agent `auto` picked a model for; "" otherwise. */
export function pickLine(a: { role: string; name: string; model: string; reason: string }): string {
  if (!a.reason) return "";
  return `picked at spawn: ${a.role || a.name}${a.model ? ` on ${a.model}` : ""} -- ${a.reason}`;
}

function asLive(a: RecordAgent): LiveAgent {
  return { key: a.key, harness: "", session: "", session_id: "", agent_id: a.id, parent: a.parent, name: a.name, role: a.role, bio: a.bio,
           lineup: a.lineup, model: a.model, state: a.state, task: a.task, current: a.current, cost_usd: a.cost || 0, since: a.started || 0,
           activity: "", tool: "", calls: 0, control: "all" };
}

/** The record as the Live page's nodes (orphans under one "unknown parent" node). */
export function liveNodes(rec: WorkRecord, st: FleetState, graph: GraphNode[], lineup: string, now = Date.now()): LiveNode[] {
  const out: LiveNode[] = rec.agents.map((a) => {
    const ref = findAgent(st, a.key);
    const activity = ref ? activityOf(ref, st, now) : "";
    const card = matchNode(asLive(a), graph, lineup);
    return {
      id: a.id, key: a.key, parent: a.orphan ? UNKNOWN : a.parent, name: a.name, role: a.role, model: a.model, state: a.state, pick: pickLine(a),
      activity, glow: glowOf(activity), card: card?.id || "", cardLabel: card ? cardKey(card) : "", task: a.task, current: a.current,
      cost: a.cost, started: a.started, ended: a.ended,
      ...(a.row.square ? { square: a.row.square.name, engine: a.row.square.engine } : {}),
    };
  });
  if (rec.agents.some((a) => a.orphan))
    out.unshift({ id: UNKNOWN, key: "", parent: null, name: "unknown parent", role: "", model: "", state: "", activity: "", glow: "", card: "", cardLabel: "",
                  task: "these agents name a parent that is not in this session's frames", current: "", cost: null, started: null, ended: null, pick: "", virtual: true });
  return withGroups(out, rec, roles.get().graph?.tiers || []);
}

/** The session Live draws: the one asked for while it is listed, else this harness's newest. */
export function liveSession(st: FleetState, want: string): string {
  const refs = recordRefs(st);
  return want && refs.some((r) => r.id === want) ? want : refs[0]?.id || "";
}

/** A node clicked: the agent selected, and the inspector says it (3.3.16.0 R2: Live's pick, routes/agents/live/scope.ts). */
export function selectLive(key: string): void {
  if (!key) return;
  select(key);
  watchAgent(key);
  openLiveTab();
  pickLive("agent", key);
}

/** J / K in Live: the next / previous working agent, in tree order. */
export function hopLive(dir: 1 | -1): void {
  const st = fleet.get();
  const rec = sessionRecord(st, liveSession(st, roles.get().liveSid));
  const order = rec ? rec.agents.filter((a) => WORKING.includes(a.state)).map((a) => a.key)
    : allAgents(st).filter((r) => WORKING.includes(String(r.a.state || ""))).map((r) => r.key);
  if (!order.length) return;
  const i = order.indexOf(roles.get().watched);
  selectLive(order[i < 0 ? (dir > 0 ? 0 : order.length - 1) : (i + dir + order.length) % order.length]);
}

/** The Session Map's expand: Roles, Live, on that session. */
export function openRolesLive(sid: string, go: () => void): void {
  roles.update(() => ({ canvasView: "live", liveSid: sid, view: "workspace" }));
  go();
}
