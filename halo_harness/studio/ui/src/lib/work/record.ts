// The work record adapter (3.3.11.0 R2; the ROADMAP's "One record, many views": every Studio surface that
// shows agents reads them through THIS file, so the switch to the shared work record of Federation R1 --
// `<state>/work/<id>.json`, versioned, the same shape -- is a change here and nowhere else). Today the record
// is read from the fleet frames (routes/fleet: GET fleet, then the feed): one session's agent tree as
//
//   {id, harness, title, kind, agents: [{id, key, parent, name, role, model, state, reason, started, ended,
//    task, current, cost, lineup, bio, orphan, row}], edges: [{from, to}]}
//
// in the session's own order (the registry's: parents before their children). `parent` is the id the agent
// names; `orphan` says that id is not in the record (a background job that never announced: the views hang it
// under "unknown parent", never drop it); `edges` join only the parents that are in it. `ended` is when it
// finished (seconds; the feed's done time, else null). `row` is the frame's own agent row, for the views that
// draw more of it (the Map's node). Readers: the Session Map (routes/fleet/layoutTree.ts) and Roles Live
// (routes/roles/liveModel.ts).
import { useMemo } from "react";
import { keyOf, localId, sessionTitle, useFleet, type FleetState } from "../../routes/fleet/store";
import type { AgentRow, Harness, SessionRow } from "../../routes/fleet/types";

export type RecordAgent = {
  id: string; key: string; parent: string | null; name: string; role: string; model: string; state: string; reason: string;
  started: number | null; ended: number | null; task: string; current: string; cost: number | null; lineup: string; bio: string;
  orphan: boolean; row: AgentRow;
};
export type RecordEdge = { from: string; to: string };
export type WorkRecord = {
  id: string; harness: string; harnessName: string; local: boolean; title: string; kind: string; started: number | null;
  agents: RecordAgent[]; edges: RecordEdge[];
};
/** One line of the session picker: a session that has a record. */
export type RecordRef = { harness: string; id: string; title: string; local: boolean; kind: string; started: number; live: number };

const num = (v: unknown): number | null => (typeof v === "number" && isFinite(v) ? v : null);
const FINISHED = ["done", "failed", "stopped"];

/** The record of one session row (`doneAt`: the feed's done times by agent key, ms). */
export function recordOf(h: Harness, s: SessionRow, doneAt: Record<string, number> = {}): WorkRecord {
  const rows = (s.agents || []).filter((a) => a && a.agent_id);
  const ids = new Set(rows.map((a) => a.agent_id));
  const agents: RecordAgent[] = rows.map((a) => {
    const key = keyOf(h.id, s.session_id, a.agent_id);
    const parent = a.parent && a.parent !== a.agent_id ? String(a.parent) : null;
    const state = String(a.state || "");
    return {
      id: a.agent_id, key, parent, name: String(a.name || a.agent_id), role: String(a.role || ""), model: String(a.model || ""), state,
      reason: String(a.model_reason || ""), started: num(a.since), ended: FINISHED.includes(state) ? (doneAt[key] ? doneAt[key] / 1000 : null) : null,
      task: String(a.task || ""), current: String(a.current || ""), cost: num(a.cost_usd), lineup: String(a.lineup || ""), bio: String(a.bio || ""),
      orphan: !!parent && !ids.has(parent), row: a,
    };
  });
  const edges = agents.filter((a) => a.parent && !a.orphan).map((a) => ({ from: a.parent as string, to: a.id }));
  return {
    id: s.session_id, harness: h.id, harnessName: String(h.name || h.id.slice(0, 8)), local: !!h.local, title: sessionTitle(s),
    kind: String(s.kind || "tui"), started: num(s.started), agents, edges,
  };
}

/** The record of session `sid` (of harness `hid`, else of whichever lists it first), or null. */
export function sessionRecord(st: FleetState, sid: string, hid = ""): WorkRecord | null {
  for (const h of st.harnesses) {
    if (hid && h.id !== hid) continue;
    const s = (h.sessions || []).find((x) => x.session_id === sid);
    if (s) return recordOf(h, s, st.doneAt);
  }
  return null;
}

/** Every session that has a record: this harness first, then the newest first. */
export function recordRefs(st: FleetState): RecordRef[] {
  const here = localId(st);
  const out: RecordRef[] = [];
  for (const h of st.harnesses)
    for (const s of h.sessions || [])
      out.push({ harness: h.id, id: s.session_id, title: sessionTitle(s), local: h.id === here, kind: String(s.kind || "tui"),
                 started: Number(s.started) || 0, live: (s.agents || []).filter((a) => !FINISHED.includes(String(a.state || ""))).length });
  return out.sort((a, b) => Number(b.local) - Number(a.local) || b.started - a.started || (a.id < b.id ? -1 : 1));
}

/** The session's record, recomputed when the fleet's sessions or done times move. */
export function useSessionRecord(sid: string, hid = ""): WorkRecord | null {
  const harnesses = useFleet((s) => s.harnesses);
  const doneAt = useFleet((s) => s.doneAt);
  return useMemo(() => (sid ? sessionRecord({ harnesses, doneAt } as FleetState, sid, hid) : null), [harnesses, doneAt, sid, hid]);
}
