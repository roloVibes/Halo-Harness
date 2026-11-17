// What lights the Map now (3.6.0.2 R55: the Map is the plan, no run overlay): only a replay opened from the Map's History
// (mapRuns.ts) at the scrubber's moment, through the overlay (overlay.ts), in quiet colours. A running session is drawn
// in Agents -> 4 · Live (agents/liveLit.tsx gives Live's session in this same shape through LitCtx); on the Map it is one
// quiet line (NoticeRow.tsx). `all`: this machine's running sessions (History leaves them out of its finished runs).
import { createContext, useContext, useEffect, useMemo } from "react";
import { useStore } from "../../../lib/store";
import type { WorkRecord } from "../../../lib/work/record";
import type { LiveNode } from "../live/liveModel";
import { useLiveReplay, type LiveReplay } from "../live/replay";
import type { Change } from "../types";
import { startLit, useAway, useRunning, type AwaySession, type LitSession } from "./litStore";
import { mapHist } from "./mapRuns";
import { eventsAt, overlay, type OvMap, type OvRow, type Overlay } from "./overlay";
import { useMap } from "./mapStore";
import type { MapFile } from "./mapTypes";

export type Lit = {
  mode: "off" | "live" | "replay"; session: LitSession | null; all: LitSession[]; other: boolean; nomap: boolean; ov: Overlay | null;
  /** R4b: other machines' running sessions */
  away: AwaySession[];
  rec: WorkRecord | null; card: Change[]; replay: LiveReplay | null; map: string; now: number;
};

const NONE: Change[] = [];
export const EMPTY: OvMap = { boxes: [], lines: [] };

export const rowOfNode = (n: LiveNode): OvRow => ({
  agent_id: n.id, parent: n.parent, name: n.name, role: n.role, state: n.state, cost_usd: n.cost, current: n.current, model: n.model,
  kind: n.parent ? "subagent" : "main", square: n.square ? { name: n.square } : null,
});

/** The Map tab's Lit: a replay of History's open run, else off (R55). */
export function useLit(): Lit {
  useEffect(() => startLit(), []);
  const file: MapFile | null = useMap((s) => s.detail?.map || null);
  const shown = useMap((s) => s.name);
  const all = useRunning();
  const away = useAway();
  const r = useLiveReplay();
  const hist = useStore(mapHist, (s) => s.open);
  const replay = r && hist && r.kind === "session" && r.id === hist.sid ? r : null;
  const ov = useMemo(() => (replay && hist ? overlay(hist.map === shown && file ? file : EMPTY, replay.nodes.map(rowOfNode), eventsAt(hist.events, replay.t), replay.t) : null),
    [replay, hist, file, shown]);
  return replay ? { ...OFF, mode: "replay", all, away, ov, replay, map: hist?.map || "", now: replay.t } : { ...OFF, all, away };
}

export const OFF: Lit = { mode: "off", session: null, all: [], away: [], other: false, nomap: false, ov: null, rec: null, card: NONE, replay: null, map: "", now: 0 };
/** MapMain computes it once (useLit) and every part of the tab reads it here. */
export const LitCtx = createContext<Lit>(OFF);
export const useLitNow = (): Lit => useContext(LitCtx);
