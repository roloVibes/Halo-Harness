// Session's Map (Agents -> Live's thumbnail): this harness's sessions as the roots, each session's agents under the
// session as the work record holds them (lib/work/record.ts, nothing dropped: an agent whose parent is not in the
// frames hangs under its session). Node ids: `s:<harness>|<session>`, an agent's key `<harness>|<session>|<agent>`.
// Pure.
import { recordOf } from "../../../lib/work/record";
import { keyOf, sessionTitle, type FleetState } from "../../fleet/store";
import type { Harness, SessionRow } from "../../fleet/types";
import { liveNodes, UNKNOWN, type LiveNode } from "../../roles/liveModel";
import type { GraphNode } from "../../roles/types";

const BLANK = { role: "", model: "", state: "", pick: "", activity: "", glow: "" as const, card: "", cardLabel: "", task: "", current: "",
  cost: null, started: null, ended: null };

/** A session's main agent's fleet key (what a session node selects, as the Map's session card did). */
export function mainKey(h: Harness, s: SessionRow): string {
  return keyOf(h.id, s.session_id, (s.agents || []).find((a) => !a.parent)?.agent_id || "main");
}

function sessionNodes(st: FleetState, h: Harness, s: SessionRow, parent: string | null, graph: GraphNode[], lineup: string, now: number): LiveNode[] {
  const sid = `s:${h.id}|${s.session_id}`;
  const head: LiveNode = {
    ...BLANK, id: sid, key: mainKey(h, s), parent, name: sessionTitle(s), state: String(s.status || ""), kind: "session", harness: h.id, sid: s.session_id,
    task: String(s.cwd || ""), cost: typeof s.cost_usd === "number" ? s.cost_usd : null, started: Number(s.started) || null, role: s.kind === "headless" ? "no terminal" : String(s.kind || "session"),
  };
  const rec = recordOf(h, s, st.doneAt);
  const up = (p: string | null) => (p && p !== UNKNOWN ? keyOf(h.id, s.session_id, p) : sid);
  const agents = liveNodes(rec, st, graph, lineup, now).filter((n) => !n.virtual).map((n) => ({
    ...n, id: n.key, harness: h.id, sid: s.session_id, parent: up(n.parent),
    ...(n.group?.parent ? { group: { ...n.group, parent: up(n.group.parent) } } : {}), // 3.3.16.3: the box hangs under the same node
  }));
  return [head, ...agents];
}

/** This harness's sessions and their agents as the Map's nodes (`only`: the harness). */
export function fleetNodes(st: FleetState, graph: GraphNode[], lineup: string, now: number, only: string): LiveNode[] {
  const out: LiveNode[] = [];
  for (const h of st.harnesses.filter((x) => x.id === only))
    for (const s of h.sessions || []) out.push(...sessionNodes(st, h, s, null, graph, lineup, now));
  return out;
}
