// A session's live nodes (3.3.11.0 R2; 3.6.0.0 R5: the old Live tree went, the Map's top line, Session's glance and the
// waits read these): the session's real agent tree, read through the work record adapter (lib/work/record.ts) and
// nothing else. One node per agent the record holds -- live, or finished and still in the frames -- and NOTHING
// dropped: an agent whose parent is not in the record hangs under one "unknown parent" node, said. An `auto` pick
// carries its reason ("picked at spawn: coder on <model> -- <why>", the same words the TUI's `/agents live` prints).
// The glow is glow.ts's (typing / a tool -> working, waiting on you, done, failed). Pure.
import { recordRefs, type WorkRecord } from "../../../lib/work/record";
import { activityOf } from "../../fleet/frames";
import { findAgent, type FleetState } from "../../fleet/store";
import { withGroups, type GroupTag } from "./groups";
import { glowOf, type GlowState } from "./glow";

export const UNKNOWN = "?unknown-parent";

export type LiveNode = {
  id: string; key: string; parent: string | null; name: string; role: string; model: string; state: string; pick: string;
  activity: string; glow: GlowState | ""; card: string; cardLabel: string; task: string; current: string; cost: number | null;
  started: number | null; ended: number | null; virtual?: boolean;
  /** 3.4.1.1 (60): an agent whose record gives its cost at its end only, drawn before it: "cost unknown". */
  costUnknown?: boolean;
  /** 3.6.0.25 G: an agent of a Claude Code session Halo only shows: its cost is not known (Halo reads no count of it). */
  guest?: boolean;
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

/** The record as live nodes (orphans under one "unknown parent" node). */
export function liveNodes(rec: WorkRecord, st: FleetState, now = Date.now()): LiveNode[] {
  const out: LiveNode[] = rec.agents.map((a) => {
    const ref = findAgent(st, a.key);
    const activity = ref ? activityOf(ref, st, now) : "";
    return {
      id: a.id, key: a.key, parent: a.orphan ? UNKNOWN : a.parent, name: a.name, role: a.role, model: a.model, state: a.state, pick: pickLine(a),
      activity, glow: glowOf(activity), card: "", cardLabel: "", task: a.task, current: a.current,
      cost: a.cost, started: a.started, ended: a.ended, ...(rec.kind === "guest" ? { guest: true } : {}),
      ...(a.row.square ? { square: a.row.square.name, engine: a.row.square.engine } : {}),
    };
  });
  if (rec.agents.some((a) => a.orphan))
    out.unshift({ id: UNKNOWN, key: "", parent: null, name: "unknown parent", role: "", model: "", state: "", activity: "", glow: "", card: "", cardLabel: "",
                  task: "these agents name a parent that is not in this session's frames", current: "", cost: null, started: null, ended: null, pick: "", virtual: true });
  return withGroups(out, rec, []);
}

/** The session to draw: the one asked for while it is listed, else this harness's newest. */
export function liveSession(st: FleetState, want: string): string {
  const refs = recordRefs(st);
  return want && refs.some((r) => r.id === want) ? want : refs[0]?.id || "";
}
