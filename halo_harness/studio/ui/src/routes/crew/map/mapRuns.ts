// History under the Map (3.6.0.0 R4, the design: "a picker of finished runs, newest first, and the scrubber. A run
// replays ON this map in quiet colours"): the finished sessions of this harness (GET live/history?role=main, what Live's
// History lists), newest first; a pick opens it as the replay (agents/live/replay.ts: the same scrubber, the same time
// axis) and reads the map it ran on and its hand-offs and steps (GET live/replay's `map`, `map_events`: the session's
// log), so the lit Map's overlay replays it on that map. A session that ran on another map opens that map first; one
// that ran on no map replays as main and its helpers. Its report card opens from the picker row (ReportCard.tsx).
import { api, ApiError } from "../../../lib/api";
import { createStore, toast, useStore } from "../../../lib/store";
import { backToNow, openLiveReplay, replayOnMapWith } from "../live/replay";
import type { OvEvent } from "./overlay";
import { maps, openMap } from "./mapStore";
import { openMapDrawer } from "./feedOpen";

export type RunRow = { sid: string; what: string; when: number; cost: number | null };
export type OpenRun = { sid: string; title: string; map: string | null; events: OvEvent[]; removed: string[] };
type State = { rows: RunRow[]; loaded: boolean; pick: string; open: OpenRun | null; card: string; busy: boolean };

export const mapHist = createStore<State>({ rows: [], loaded: false, pick: "", open: null, card: "", busy: false });
export const useMapHist = <T,>(f: (s: State) => T): T => useStore(mapHist, f);

type Run = { session_id?: string; task?: string; started?: number; cost_usd?: number | null; part_of?: unknown };

/** The finished sessions, newest first (those running now are on the map, not here). */
export function runRows(runs: Run[], running: Set<string>): RunRow[] {
  return runs.filter((r) => r.session_id && !r.part_of && !running.has(String(r.session_id)))
    .map((r) => ({ sid: String(r.session_id), what: String(r.task || "session " + String(r.session_id).slice(0, 8)), when: Number(r.started) || 0,
                   cost: typeof r.cost_usd === "number" ? r.cost_usd : null }))
    .sort((a, b) => b.when - a.when);
}

export async function loadMapHistory(running: Set<string>): Promise<void> {
  try {
    const r = await api.get<{ runs: Run[] }>("live/history", { role: "main", n: "20" });
    const rows = runRows(r.runs || [], running);
    mapHist.update((s) => ({ rows, loaded: true, pick: s.pick && rows.some((x) => x.sid === s.pick) ? s.pick : rows[0]?.sid || "" }));
  } catch (e) {
    mapHist.update(() => ({ loaded: true }));
    toast(`History: ${e instanceof ApiError ? e.message : String(e)}`, "error", 4000);
  }
}

export const pickRun = (sid: string) => mapHist.update(() => ({ pick: sid, card: "" }));
export const toggleCard = () => mapHist.update((s) => ({ card: s.card ? "" : s.pick }));

/** Replay the picked run ON the map it ran on (that map opened first when it is another). */
export async function replayRun(sid = mapHist.get().pick): Promise<boolean> {
  const row = mapHist.get().rows.find((r) => r.sid === sid);
  if (!sid || mapHist.get().busy) return false;
  mapHist.update(() => ({ busy: true }));
  try {
    const meta = await api.get<{ map?: string | null; map_events?: OvEvent[] }>("live/replay", { session: sid, harness: "local" });
    const ran = typeof meta.map === "string" && meta.map ? meta.map : null;
    if (ran && ran !== maps.get().name && maps.get().rows.some((m) => m.name === ran)) await openMap(ran);
    const file = maps.get().detail?.map;
    const events = Array.isArray(meta.map_events) ? meta.map_events : [];
    const ids = new Set(["main", ...(file?.boxes || []).map((b) => b.id)]);
    const removed = [...new Set(events.map((e) => String(e.data.to || "")).filter((id) => id && !ids.has(id)))];
    mapHist.update(() => ({ open: { sid, title: row?.what || sid, map: ran, events, removed } }));
    const ok = await openLiveReplay("session", sid, row?.what || `session ${sid.slice(0, 8)}`);
    if (!ok) mapHist.update(() => ({ open: null }));
    else openMapDrawer("history"); // P7 (the coordinator's ruling): Replay is his press -- its rows show at once, on History's page
    return ok;
  } catch (e) {
    toast(`No replay: ${e instanceof ApiError ? e.message : String(e)}`, "error", 5000);
    return false;
  } finally {
    mapHist.update(() => ({ busy: false }));
  }
}

replayOnMapWith((sid) => replayRun(sid)); // 3.6.0.0 R5: History's and the palette's session replays land here

/** Back to what runs: the replay leaves the map. */
export function closeRun(): void {
  backToNow();
  mapHist.update(() => ({ open: null }));
}
