// The card glow's life on the Roles canvas (3.1.5.0 R3; the owner: "more
// info how that glow looks and goes"). It comes on with the agent's first
// running state (a queued agent shows its badge, no glow) and takes the
// state's colour: working cyan (a flow along the top while it types, one
// pulse per tool call), waiting amber, done green that fades out over the
// ten seconds after it finished, failed red that stays until you click the
// card. frames.ts hands the canvas the live agents (and one that ended in
// the last three seconds); this module keeps the ended ones on it for their
// glow (`ended` in the Roles store), and `GLOW` is what the card's legend
// says (GlowLegend.tsx).
import { createStore, studio, useStore } from "../../lib/store";
import { allAgents, DONE_MS, fleet, sessionTitle, toolOf, type FleetState } from "../fleet/store";
import type { AgentRef } from "../fleet/types";
import { roles } from "./store";
import type { LiveAgent } from "./types";

export type GlowState = "working" | "waiting" | "done" | "failed";

/** The legend: each state, its colour and when it comes and goes. */
export const GLOW: { state: GlowState; color: string; label: string; when: string }[] = [
  { state: "working", color: "cyan", label: "working", when: "comes on with its first running state: a flow along the top while it types, one pulse per tool call" },
  { state: "waiting", color: "amber", label: "waiting on you", when: "a question, a permission, a plan or a pause: it pulses, then holds amber until you answer" },
  { state: "done", color: "green", label: "done", when: "it finished: the green fades out over the next ten seconds" },
  { state: "failed", color: "red", label: "failed", when: "it failed: the red stays until you click the card" },
];

/** A card's activity (live.ts cardActivity) as the legend's state; "" for no glow (nothing, or only queued). */
export function glowOf(activity: string): GlowState | "" {
  if (activity === "typing" || activity === "tool" || activity === "working") return "working";
  if (activity === "waiting" || activity === "done" || activity === "failed") return activity;
  return "";
}

const acked = new Set<string>();

/** The card was clicked: its failed agents stop glowing. */
export function ackFailed(list: LiveAgent[]): void {
  let hit = false;
  for (const a of list) if (a.state === "failed" && !acked.has(a.key)) (acked.add(a.key), (hit = true));
  if (hit) push();
}

export const isAcked = (key: string) => acked.has(key);

function toLive(r: AgentRef, s: FleetState, endedAt: number): LiveAgent {
  const st = String(r.a.state || "");
  return {
    key: r.key, harness: r.h.name || r.h.id.slice(0, 8), session: sessionTitle(r.s), session_id: r.s.session_id, agent_id: r.a.agent_id,
    parent: r.a.parent || null, name: r.a.name || r.a.agent_id, role: r.a.role || "", bio: r.a.bio || "", lineup: r.a.lineup || "",
    model: r.a.model || "", state: st, task: r.a.task || "", current: r.a.current || "", cost_usd: Number(r.a.cost_usd) || 0,
    since: Number(r.a.since) || 0, activity: st === "failed" ? "failed" : "done", tool: toolOf(r.a, s.activity[r.key]),
    calls: s.activity[r.key]?.calls || 0, control: r.h.allow_control || "all", endedAt,
  };
}

/** The agents that ended but still glow: done for DONE_MS after it ended here, failed until acknowledged. */
export function endedAgents(s: FleetState = fleet.get(), now = Date.now()): LiveAgent[] {
  const out: LiveAgent[] = [];
  for (const r of allAgents(s)) {
    const st = String(r.a.state || "");
    const at = s.doneAt[r.key] || 0;
    if ((st === "done" || st === "stopped") && at && now - at < DONE_MS) out.push(toLive(r, s, at));
    else if (st === "failed" && !acked.has(r.key)) out.push(toLive(r, s, at || now));
  }
  return out;
}

let last = "";
function push(): void {
  if (studio.get().section !== "roles") return; // only while the canvas shows: nothing of it runs for Fleet or Session
  const rows = endedAgents();
  const json = JSON.stringify(rows.map((r) => [r.key, r.state, r.endedAt, r.cost_usd]));
  if (json === last) return;
  last = json;
  roles.update(() => ({ ended: rows }));
}

let started = false;

/** Start once (the canvas shows): on every fleet change and once a second (a done glow ages out). */
export function startGlow(): void {
  if (started) return;
  started = true;
  let timer = 0;
  fleet.subscribe(() => {
    window.clearTimeout(timer);
    timer = window.setTimeout(push, 120);
  });
  window.setInterval(push, 1000);
  let was = studio.get().section;
  studio.subscribe(() => {
    const now = studio.get().section;
    if (now !== was && (was = now) === "roles") push();
  });
  push();
}

// -- the legend over a hovered glow -------------------------------------------------------------
export type LegendAt = { x: number; y: number; state: GlowState | ""; card: string } | null;
export const legend = createStore<{ at: LegendAt }>({ at: null });
export const useLegend = () => useStore(legend, (s) => s.at);

export function showLegend(el: HTMLElement, state: GlowState | "", card: string): void {
  const r = el.getBoundingClientRect();
  legend.update(() => ({ at: { x: r.left, y: r.bottom + 6, state, card } }));
}

export const hideLegend = () => legend.get().at && legend.update(() => ({ at: null }));
