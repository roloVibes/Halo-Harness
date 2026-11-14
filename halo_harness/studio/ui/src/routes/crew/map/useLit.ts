// What lights the Map now (3.6.0.0 R4): the running session picked by litStore.ts on the map it started with, or a
// replay opened from the Map's History (mapRuns.ts) at the scrubber's moment -- both through the same overlay
// (overlay.ts). `other`: the lit session runs on another map than the one shown (the top line says so, in amber, with
// "Show the running map"; the shown map is not lit). `nomap`: a session that did not start on a map (main and its
// helpers, as made-up helpers, on an empty map). `card`: a Builder card the session parked (its ghosts on the map).
import { createContext, useContext, useEffect, useMemo } from "react";
import { useStore } from "../../../lib/store";
import { useSessionRecord, type WorkRecord } from "../../../lib/work/record";
import { useNow } from "../../fleet/store";
import type { LiveNode } from "../../roles/liveModel";
import { useLiveReplay, type LiveReplay } from "../../agents/live/replay";
import type { Change } from "../types";
import { chosen, lit, startLit, useRunning, type LitSession } from "./litStore";
import { mapHist } from "./mapRuns";
import { eventsAt, overlay, type OvMap, type OvRow, type Overlay } from "./overlay";
import { useMap } from "./mapStore";
import type { MapFile } from "./mapTypes";

export type Lit = {
  mode: "off" | "live" | "replay"; session: LitSession | null; all: LitSession[]; other: boolean; nomap: boolean; ov: Overlay | null;
  rec: WorkRecord | null; card: Change[]; replay: LiveReplay | null; map: string; now: number;
};

const NONE: Change[] = [];
export const EMPTY: OvMap = { boxes: [], lines: [] };

export const rowOfNode = (n: LiveNode): OvRow => ({
  agent_id: n.id, parent: n.parent, name: n.name, role: n.role, state: n.state, cost_usd: n.cost, current: n.current, model: n.model,
  kind: n.parent ? "subagent" : "main", square: n.square ? { name: n.square } : null,
});

export function useLit(): Lit {
  useEffect(() => startLit(), []);
  const file: MapFile | null = useMap((s) => s.detail?.map || null);
  const shown = useMap((s) => s.name);
  const all = useRunning();
  const pick = useStore(lit, (s) => s.pick);
  const r = useLiveReplay();
  const hist = useStore(mapHist, (s) => s.open);
  const replay = r && hist && r.kind === "session" && r.id === hist.sid ? r : null;
  const session = replay ? null : chosen(all, pick, shown);
  const rec = useSessionRecord(session?.sid || "");
  const events = useStore(lit, (s) => (session ? s.events[session.sid] : undefined));
  const card = useStore(lit, (s) => (session ? s.cards[session.sid]?.changes : undefined)) || NONE;
  const wall = useNow(!!session, 1000) / 1000;
  const other = !!session && !!session.map && session.map !== shown;
  const nomap = !!session && !session.map;
  const ov = useMemo(() => {
    if (replay && hist) return overlay(hist.map === shown && file ? file : EMPTY, replay.nodes.map(rowOfNode), eventsAt(hist.events, replay.t), replay.t);
    if (!session || other || !file) return null;
    const rows: OvRow[] = (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }) as OvRow);
    return overlay(nomap ? EMPTY : file, rows, events || [], wall);
  }, [replay, hist, session, other, nomap, file, rec, events, wall, shown]);
  const mode = replay ? "replay" : session ? "live" : "off";
  return { mode, session, all, other, nomap, ov, rec, card: other ? NONE : card, replay, map: replay ? hist?.map || "" : session?.map || "", now: replay ? replay.t : wall };
}

export const OFF: Lit = { mode: "off", session: null, all: [], other: false, nomap: false, ov: null, rec: null, card: NONE, replay: null, map: "", now: 0 };
/** MapMain computes it once (useLit) and every part of the tab reads it here. */
export const LitCtx = createContext<Lit>(OFF);
export const useLitNow = (): Lit => useContext(LitCtx);
