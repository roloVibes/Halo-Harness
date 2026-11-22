// The lit Map's session (3.6.0.0 R4, docs/STUDIO-map.md "While a session runs"): which session lights the map, and the
// map frames each session sent (crew/map_events.py: map_hop, map_step, map_card), kept here as they arrive on the feed
// (lib/events.ts). A session is "running" while any of its agents is live (GET fleet's rows). The map lit is the one
// the session started with (its row's `map`); one session is lit at a time: the one picked in the top line, else the
// newest one running on the map open here, else the newest running on any map. A session that did not start on a map
// is lit only when picked (the map he built is never covered by a session that is not on it). 3.6.0.2 R2: an OPEN session
// is shown (`open`, `openList`), busy only lights its boxes; `running` / `useRunning` stay for Agents -> Map (P4).
import { useMemo } from "react";
import { onEvent, type FeedFrame } from "../../../lib/events";
import { createStore, useStore } from "../../../lib/store";
import { localId, useFleet, type FleetState } from "../../fleet/store";
import type { SessionRow } from "../../fleet/types";
import { openOrder } from "../../session/pick";
import type { Change } from "../types";
import type { OvEvent } from "./overlay";
import { takeBuilt } from "./built";
import { batcher } from "./frameBatch";
import { foldHop, NO_TOTALS, type Totals } from "./overlayHops";
import { isAuto, onMap } from "./truthWords";

export const MAX_EVENTS = 600; // the window of recent frames; the trace's totals (overlayHops.ts) are kept apart, exact (R49)
/** `plain`: the session runs on the default map (R17); `busy`: its row says a turn runs (R16: no hand-off live once not). */
export type LitSession = { sid: string; title: string; map: string | null; started: number; live: number; plain?: boolean; busy?: boolean;
  /** 3.6.0.2 R50: the file the session follows (its row's `map_scope`, `map_path`), for the drawing's one soft read */
  scope?: string | null; path?: string | null;
  /** 3.6.0.5 B1: the row says the session runs on the PlainMap (`map_plain`) AND names the default (isAuto): drawn as main
   *  and its groups; a row naming a map of his, or no map at all, keeps its drawing; B30: `map_agents`, the agents it had at its start (main's hover G5) */
  auto?: boolean; map_agents?: string[];
  /** 3.6.0.13 L3: the kinds main was told it can start (`kinds_told`, `kinds_more`); null before its first request */
  told?: { names: string[]; more: number } | null };
type State = { events: Record<string, OvEvent[]>; totals: Record<string, Totals>; cards: Record<string, { id: string; changes: Change[] }>;
  pick: string; feed: string; feedFor: string;
  /** 3.6.0.5 B27: the group a card's [Open in Agents -> Live] asked for, taken once by that session's drawing */
  focus: { sid: string; n: number } | null };

export const lit = createStore<State>({ events: {}, totals: {}, cards: {}, pick: "", feed: "", feedFor: "", focus: null });
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
  push({ sid, ev: { event: f.event, data: { ...d, seen: Date.now() / 1000 } } });
}

// R49: the frames that arrive within one animation frame are merged in one update (one draw, not one per frame); a
// timer flushes too, so a hidden tab (no animation frames) never piles them up (frameBatch.ts)
const push = batcher(apply, {
  raf: typeof requestAnimationFrame === "function" ? (f) => requestAnimationFrame(f) : undefined,
  timer: (f, ms) => setTimeout(f, ms), hidden: () => typeof document !== "undefined" && document.hidden });
function apply(got: { sid: string; ev: OvEvent }[]): void {
  lit.update((s) => {
    const events = { ...s.events }, totals = { ...s.totals };
    for (const { sid, ev } of got) {
      events[sid] = [...(events[sid] || []), ev];
      if (ev.event === "map_hop") totals[sid] = foldHop(totals[sid] || NO_TOTALS, ev);
    }
    for (const sid of new Set(got.map((x) => x.sid))) if (events[sid].length > MAX_EVENTS) events[sid] = events[sid].slice(-MAX_EVENTS);
    return { events, totals };
  });
}

let bound = false;
/** Hear the map frames (once a page). */
export function startLit(): void {
  if (bound) return;
  bound = true;
  onEvent("map_hop", take);
  onEvent("map_step", take);
  onEvent("map_card", take);
  // 3.6.0.2 R29-R32: what a Builder card in a session just built (built.ts); nothing it does opens or changes a section
  onEvent("builder_done", (f) => takeBuilt(f.session_id || "", (f.data || {}) as Record<string, unknown>));
}

/** A session row as the lit drawing takes it: `live` (its agents at work, + 1 while busy) only lights boxes. */
export function toLit(s: SessionRow): LitSession {
  const live = (s.agents || []).filter((a) => LIVE.includes(String(a.state || ""))).length + (s.busy ? 1 : 0);
  const map = typeof s.map === "string" && s.map ? s.map : null;
  return { sid: s.session_id, title: String(s.title || s.session_id.slice(0, 8)), map, started: Number(s.started) || 0, live,
           plain: !map || !!s.map_plain, busy: !!s.busy, scope: s.map_scope ?? null, path: s.map_path ?? null,
           auto: !!s.map_plain && isAuto(map), map_agents: Array.isArray(s.map_agents) ? s.map_agents.map(String) : [],
           told: Array.isArray(s.kinds_told) ? { names: s.kinds_told.map(String), more: Number(s.kinds_more) || 0 } : null };
}

const here_ = (st: Pick<FleetState, "harnesses">, here: string): SessionRow[] =>
  st.harnesses.filter((h) => h.id === here || h.local).flatMap((h) => h.sessions || []);
const newestFirst = (a: LitSession, b: LitSession) => b.started - a.started || (a.sid < b.sid ? -1 : 1);

/** This harness's sessions with an agent at work (newest first). */
export function running(st: Pick<FleetState, "harnesses">, here: string): LitSession[] {
  return here_(st, here).map(toLit).filter((s) => s.live).sort(newestFirst);
}

/** 3.6.0.2 R2: open = shown: every alive row of this harness (newest first), busy or not. */
export function open(st: Pick<FleetState, "harnesses">, here: string): LitSession[] {
  return here_(st, here).map(toLit).sort(newestFirst);
}

/** R56: the open rows of this harness as they are (Agents' opening tab counts the ones he has talked to). */
export function openRows(st: Pick<FleetState, "harnesses">, here: string): SessionRow[] {
  return here_(st, here);
}

/** R2, R5: Live's picker: the open rows newest first, every Studio-started one with no message yet (T10) last. */
export function openList(st: Pick<FleetState, "harnesses">, here: string): LitSession[] {
  return openOrder(here_(st, here)).map(toLit);
}

/** The session lit for the map `shown`: the picked one while it runs, else on `shown`, else on any map. */
export function chosen(all: LitSession[], pick: string, shown: string): LitSession | null {
  return all.find((s) => s.sid === pick) || all.find((s) => !!s.map && onMap(s.map, shown)) || all.find((s) => !!s.map) || null;
}

/** Does a session whose row names `rowMap` draw the map `show` names as its own (3.6.0.5: the default's names are one map,
 *  through onMap / isAuto); no `show`: its own map. */
export const ownsMap = (rowMap: string | null, show?: { map: string }): boolean => !show || onMap(rowMap, show.map);

/** R4b (R4's gap 4): another machine's sessions with an agent at work, from the rows Studio already has. Their map
 *  frames do not reach this page (they ride that machine's feed), so the picker lists them, "open it on that machine". */
export type AwaySession = { sid: string; title: string; machine: string };
export function awayRunning(st: Pick<FleetState, "harnesses">, here: string): AwaySession[] {
  const out: AwaySession[] = [];
  for (const h of st.harnesses) {
    if (h.id === here || h.local) continue;
    for (const s of h.sessions || [])
      if ((s.agents || []).some((a) => LIVE.includes(String(a.state || ""))) || s.busy)
        out.push({ sid: s.session_id, title: String(s.title || s.session_id.slice(0, 8)), machine: String(h.name || h.id.slice(0, 8)) });
  }
  return out;
}

/** R3: another machine's open sessions (every alive row, busy or not), for Agents -> Live's picker. */
export function openAway(st: Pick<FleetState, "harnesses">, here: string): AwaySession[] {
  const out: AwaySession[] = [];
  for (const h of st.harnesses) {
    if (h.id === here || h.local) continue;
    for (const s of h.sessions || []) out.push({ sid: s.session_id, title: String(s.title || s.session_id.slice(0, 8)), machine: String(h.name || h.id.slice(0, 8)) });
  }
  return out;
}

export function useOpenAway(): AwaySession[] {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  return useMemo(() => openAway({ harnesses }, here), [harnesses, here]);
}

export function useOpen(): LitSession[] {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  return useMemo(() => open({ harnesses }, here), [harnesses, here]);
}

export function useAway(): AwaySession[] {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  return useMemo(() => awayRunning({ harnesses }, here), [harnesses, here]);
}

export function useRunning(): LitSession[] {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  return useMemo(() => running({ harnesses }, here), [harnesses, here]);
}

export const pickSession = (sid: string) => lit.update(() => ({ pick: sid }));
/** The drawer's filter: a box id, or "" for everyone. */
export const setFeedFor = (box: string) => lit.update(() => ({ feedFor: box }));
/** B27: store the group a card's Open in Agents -> Live names; Agents -> Live brings it to the top. */
export const focusGroup = (sid: string, n: number) => lit.update(() => ({ focus: { sid, n } }));
/** B27: the group stored for session `sid` (cleared once taken), else null. */
export function takeFocus(sid: string): number | null {
  const f = lit.get().focus;
  if (!f || f.sid !== sid) return null;
  lit.update(() => ({ focus: null }));
  return f.n;
}
