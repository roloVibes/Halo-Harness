// The lit Map's session (3.6.0.0 R4, docs/STUDIO-map.md "While a session runs"): which session lights the map, and the
// map frames each session sent (crew/map_events.py: map_hop, map_step, map_card), kept here as they arrive on the feed
// (lib/events.ts). A session is "running" while any of its agents is live (GET fleet's rows). The map lit is the one
// the session started with (its row's `map`); one session is lit at a time: the one picked in the top line, else the
// newest one running on the map open here, else the newest running on any map. A session that did not start on a map
// is lit only when picked (the map he built is never covered by a session that is not on it).
import { useMemo } from "react";
import { onEvent, type FeedFrame } from "../../../lib/events";
import { createStore, useStore } from "../../../lib/store";
import { localId, useFleet, type FleetState } from "../../fleet/store";
import type { Change } from "../types";
import type { OvEvent } from "./overlay";

export const MAX_EVENTS = 600;
export type LitSession = { sid: string; title: string; map: string | null; started: number; live: number };
type State = { events: Record<string, OvEvent[]>; cards: Record<string, { id: string; changes: Change[] }>; pick: string; feed: string; feedFor: string };

export const lit = createStore<State>({ events: {}, cards: {}, pick: "", feed: "", feedFor: "" });
export const useLitStore = <T,>(f: (s: State) => T): T => useStore(lit, f);
const LIVE = ["queued", "running", "waiting", "paused"];

function take(f: FeedFrame): void {
  const sid = f.session_id || "";
  const d = (f.data || {}) as Record<string, unknown>;
  if (!sid) return;
  if (f.event === "map_card") {
    lit.update((s) => {
      const cards = { ...s.cards };
      if (d.done) delete cards[sid];
      else cards[sid] = { id: String(d.id || ""), changes: (Array.isArray(d.changes) ? d.changes : []) as Change[] };
      return { cards };
    });
    return;
  }
  lit.update((s) => ({ events: { ...s.events, [sid]: [...(s.events[sid] || []), { event: f.event, data: { ...d, seen: Date.now() / 1000 } }].slice(-MAX_EVENTS) } }));
}

let bound = false;
/** Hear the map frames (once a page). */
export function startLit(): void {
  if (bound) return;
  bound = true;
  onEvent("map_hop", take);
  onEvent("map_step", take);
  onEvent("map_card", take);
}

/** This harness's sessions with an agent at work (newest first). */
export function running(st: Pick<FleetState, "harnesses">, here: string): LitSession[] {
  const out: LitSession[] = [];
  for (const h of st.harnesses) {
    if (h.id !== here && !h.local) continue;
    for (const s of h.sessions || []) {
      const live = (s.agents || []).filter((a) => LIVE.includes(String(a.state || ""))).length + (s.busy ? 1 : 0);
      if (!live) continue;
      const map = typeof s.map === "string" && s.map ? s.map : null;
      out.push({ sid: s.session_id, title: String(s.title || s.session_id.slice(0, 8)), map, started: Number(s.started) || 0, live });
    }
  }
  return out.sort((a, b) => b.started - a.started || (a.sid < b.sid ? -1 : 1));
}

/** The session lit for the map `shown`: the picked one while it runs, else on `shown`, else on any map. */
export function chosen(all: LitSession[], pick: string, shown: string): LitSession | null {
  return all.find((s) => s.sid === pick) || all.find((s) => s.map && s.map === shown) || all.find((s) => !!s.map) || null;
}

export function useRunning(): LitSession[] {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  return useMemo(() => running({ harnesses }, here), [harnesses, here]);
}

export const pickSession = (sid: string) => lit.update(() => ({ pick: sid }));
/** The drawer's filter: a box id, or "" for everyone. */
export const setFeedFor = (box: string) => lit.update(() => ({ feedFor: box }));
