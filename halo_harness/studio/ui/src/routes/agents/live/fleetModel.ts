// Agents -> Live, the fleet scope's tree (3.3.16.0 R2 "the Fleet fold"; the Fleet Map and its Tree panel drew this
// before): one machine node per harness (this one first), its sessions under it, each session's agents under the
// session as the work record holds them (lib/work/record.ts, nothing dropped: an agent whose parent is not in the
// frames hangs under its session), and the open mission's parts under the machine each runs on (a part nobody can run
// under this machine, its chip says so). Node ids are unique across the fleet: `m:<harness>`, `s:<harness>|<session>`,
// an agent's fleet key `<harness>|<session>|<agent>`, `p:<part>`. Session's Map is the same tree for this harness alone
// (`only`), without the machine node. Pure.
import { recordOf } from "../../../lib/work/record";
import { keyOf, sessionTitle, type FleetState } from "../../fleet/store";
import type { Harness, SessionRow } from "../../fleet/types";
import { partState, type View } from "../../fleet/mstore";
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

function partNodes(v: View | null, machines: Set<string>, local: string): LiveNode[] {
  if (!v?.plan) return [];
  return v.plan.parts.map((p) => {
    const run = v.mission.parts?.[p.id];
    const on = run?.harness || p.harness || "";
    return {
      ...BLANK, id: `p:${p.id}`, key: "", parent: `m:${machines.has(on) ? on : local}`, name: p.title, role: p.kind, state: partState(v, p.id),
      kind: "part" as const, harness: machines.has(on) ? on : local, task: p.unassignable || p.reason || p.brief,
      cost: run?.cost_usd ?? p.est_cost_usd, started: run?.started || null, ended: run?.ended || null,
    };
  });
}

/** The fleet as Live's nodes (`only`: one harness, its sessions as the roots, no machine node). */
export function fleetNodes(st: FleetState, graph: GraphNode[], lineup: string, now: number, v: View | null, only = ""): LiveNode[] {
  const hs = [...st.harnesses].sort((a, b) => Number(!!b.local) - Number(!!a.local)).filter((h) => !only || h.id === only);
  const out: LiveNode[] = [];
  for (const h of hs) {
    const mid = `m:${h.id}`;
    if (!only)
      out.push({ ...BLANK, id: mid, key: "", parent: null, name: String(h.name || h.id.slice(0, 8)), kind: "machine", harness: h.id,
                 state: h.local ? "here" : h.online ? "online" : "away", task: String(h.host || ""), role: String(h.version || "") });
    for (const s of h.sessions || []) out.push(...sessionNodes(st, h, s, only ? null : mid, graph, lineup, now));
  }
  if (!only) out.push(...partNodes(v, new Set(hs.map((h) => h.id)), hs[0]?.id || ""));
  return out;
}
