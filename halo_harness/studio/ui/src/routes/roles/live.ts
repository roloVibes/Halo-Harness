// Live Roles on the React canvas (3.0.7.0 R2; the framed page's live.js
// before): routes/fleet/frames.ts puts every live agent of every harness
// (and one that just finished) into the store; each is matched to the card
// it runs under -- the lineup must be the open one, then its alias, its bio,
// a role only one card has, and the main card for an agent with no parent --
// and the card glows by what the agent does now (typing, a tool, waiting on
// you, done, failed), with a count when several share it and their cost.
// J / K hop across the working cards (and across the agents of one card)
// with the Inspector's Live tab open on the agent; a replay (Replay.tsx)
// stands in for the live agents while it plays.
import { useMemo } from "react";
import { patchPanel, focusPanel } from "../../lib/workspace/persist";
import { watch } from "../fleet/streams";
import { roles, useRoles, type RolesState } from "./store";
import type { GraphNode, LiveAgent, Replay } from "./types";

const LIVE = ["queued", "running", "waiting", "paused"];
const RANK: Record<string, number> = { failed: 7, waiting: 6, tool: 5, typing: 4, working: 4, done: 3, queued: 1 };

export const isLiveAgent = (a: LiveAgent) => LIVE.includes(a.state);
const norm = (v: string | undefined) => String(v || "").trim().toLowerCase();

export function matchNode(a: LiveAgent, nodes: GraphNode[], lineup: string): GraphNode | null {
  if (a.lineup && lineup && norm(a.lineup) !== norm(lineup)) return null;
  const byRole = (r: string) => nodes.filter((n) => norm(n.role) === norm(r));
  return (
    nodes.find((n) => a.role && n.alias && norm(n.alias) === norm(a.role)) ||
    nodes.find((n) => a.bio && norm(n.agent) === norm(a.bio)) ||
    (a.role && byRole(a.role).length === 1 ? byRole(a.role)[0] : null) ||
    (!a.parent ? nodes.find((n) => n.role === "main") || null : null)
  );
}

/** Every agent on the canvas right now: the replay's at its clock, else the live ones. */
export function agentsNow(s: RolesState): LiveAgent[] {
  return s.replay ? agentsAt(s.replay, s.replay.t) : s.live;
}

export function byNodeOf(s: RolesState): Record<string, LiveAgent[]> {
  const out: Record<string, LiveAgent[]> = {};
  const nodes = s.graph?.nodes || [];
  for (const a of agentsNow(s)) {
    const n = matchNode(a, nodes, s.name);
    if (n) (out[n.id] = out[n.id] || []).push(a);
  }
  return out;
}

/** The card -> agents map, recomputed only when the agents or the graph change. */
export function useByNode(): Record<string, LiveAgent[]> {
  const live = useRoles((s) => s.live);
  const replay = useRoles((s) => s.replay);
  const graph = useRoles((s) => s.graph);
  const name = useRoles((s) => s.name);
  return useMemo(() => byNodeOf({ ...roles.get(), live, replay, graph, name }), [live, replay, graph, name]);
}

export function cardActivity(list: LiveAgent[]): string {
  return list.reduce((best, a) => ((RANK[a.activity] || 0) > (RANK[best] || 0) ? a.activity : best), "");
}

/** The Inspector shows the Live tab, open and focused. */
export function openLiveTab(): void {
  roles.update(() => ({ tab: "live" }));
  patchPanel("roles", "roles-inspector", { collapsed: false, face: "detail" }, false);
}

/** Watch an agent's stream in the Live tab (its backlog, then the feed). */
export function watchAgent(key: string): void {
  roles.update(() => ({ watched: key }));
  if (key && !key.startsWith("replay|")) watch(key);
}

/** A card was clicked: it is selected; with an agent on it the Live tab opens on that agent. */
export function selectCard(id: string): void {
  const s = roles.get();
  const list = id ? byNodeOf(s)[id] || [] : [];
  roles.update(() => ({ sel: id }));
  if (list.length && !s.replay) {
    const pick = list.find((a) => a.key === s.watched) || list.find(isLiveAgent) || list[0];
    watchAgent(pick.key);
    openLiveTab();
  } else if (s.tab === "live") roles.update(() => ({ watched: "" }));
}

/** J / K: the next / previous working card (or the next agent on the same card), its Live tab open. */
export function hopCard(dir: 1 | -1): void {
  const s = roles.get();
  const map = byNodeOf(s);
  const working = (id: string) => (map[id] || []).filter(isLiveAgent);
  const here = working(s.sel);
  const i = here.findIndex((a) => a.key === s.watched);
  if (s.tab === "live" && here.length > 1 && i >= 0 && i + dir >= 0 && i + dir < here.length) return watchAgent(here[i + dir].key);
  const order = (s.graph?.nodes || []).map((n) => n.id).filter((id) => working(id).length);
  if (!order.length) return;
  const ci = order.indexOf(s.sel);
  const next = order[ci < 0 ? (dir > 0 ? 0 : order.length - 1) : (ci + dir + order.length) % order.length];
  const list = working(next);
  roles.update(() => ({ sel: next }));
  watchAgent(dir > 0 ? list[0].key : list[list.length - 1].key);
  openLiveTab();
  focusPanel("roles", "roles-graph");
}

// -- the replay's agents at time t -----------------------------------------------------------
export function agentsAt(r: Replay, t: number): LiveAgent[] {
  const out: LiveAgent[] = [];
  for (const a of r.meta.agents || []) {
    const aid = String(a.agent_id || "");
    let last: Replay["events"][number] | null = null;
    let calls = 0;
    for (const e of r.events) {
      if (e.t > t) break;
      if (e.agent_id !== aid) continue;
      last = e;
      if (e.activity === "tool") calls += 1;
    }
    if (!last) continue;
    const ended = last.state === "done" || last.state === "failed";
    out.push({
      key: `replay|${r.meta.session_id}|${aid}`, harness: r.meta.harness || "", session: r.meta.title || "", session_id: r.meta.session_id, agent_id: aid,
      parent: (a.parent as string) || null, name: String(a.name || aid), role: String(a.role || ""), bio: String(a.bio || ""), lineup: String(a.lineup || ""),
      model: String(a.model || ""), state: last.state, task: String(a.task || ""), current: last.tool || "", cost_usd: ended ? Number(a.cost_usd) || 0 : 0,
      since: 0, activity: last.activity || (last.state === "running" ? "typing" : last.state), tool: last.tool || "", calls, control: "none",
    });
  }
  return out;
}
