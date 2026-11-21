// Agents -> 3 · Map and what changes the map new sessions use, or the maps, from elsewhere (3.6.0.2 R55, R21, R33):
// - the hand switch "New sessions run on this" (POST crew/map/<name>/use): its receipt is S13 naming the open session
//   that keeps its own map, "New sessions run on {B}." with none open (truth.ts);
// - a map a session's Builder card wrote (`builder_done`, R25): never drawn here yet -> `writeLocal(LAST, name)` only,
//   so the tab's first draw opens it (no fetch); drawn but not on screen -> the same, and it is opened (or re-read) when
//   he comes back to the Map; on screen, the same map with no unsaved edit -> its detail re-read in place keeping his
//   pick and When card; on screen with another map, the new-map draft or a When card -> the notice L4 in the row reserved
//   for it (NoticeRow.tsx) with [Open it]. Never `goSection`, never a pop-up, nothing in front of him moves;
// - 3.6.0.9 V: the open map follows its files, whoever wrote them: its own file, or a workflow or agent file one of its
//   boxes names (the hashes the detail holds, `sig` / `deps`, against the watcher's: studio/files_live.py), is re-read in
//   place (`rereadDetail`: the pick, the When card, the open boxes stay), after a drag in hand is dropped. The tab's own
//   save (its hash already held) reads nothing; a Locked map is read too; a removed open map is left as it is.
import { api } from "../../../lib/api";
import { createStore, studio, useStore, writeLocal } from "../../../lib/store";
import { onEvent } from "../../../lib/events";
import { onFilesChanged, type FilesChange } from "../../../lib/filesLive";
import { whenDropped } from "./drag";
import { fleet, localId } from "../../fleet/store";
import { agents, setAgentsView } from "../../agents/store";
import { pickLive } from "../../agents/livePick";
import { LAST, loadMaps, maps, msg, openMap, rereadDetail } from "./mapStore";
import { openOn } from "./mapQuiet";
import { mapName, newSessionsRunOn, s13For } from "./truth";
import { onMap } from "./truthWords";

export type Notice = { map: string; session: string; t: number };
type State = { notice: Notice | null; pending: Notice | null; drafting: boolean; drawn: boolean };
export const mapBuilt = createStore<State>({ notice: null, pending: null, drafting: false, drawn: false });
export const useMapBuilt = <T,>(pick: (s: State) => T): T => useStore(mapBuilt, pick);

/** The hand switch (R55: S13 names the open session; R24's words). The server's `moved` clause follows the sentence. */
export async function setUse(on: boolean): Promise<void> {
  const s = maps.get();
  try {
    const r = await api.post<{ undo_id: string; in_use: string | null; said?: string }>(`crew/map/${s.name}/use`, { on });
    const moved = (/keeps its own; (.+?)\.?$/.exec(r.said || "")?.[1] || "").trim();
    const tail = moved ? ` ${moved[0].toUpperCase()}${moved.slice(1)}.` : "";
    const st = fleet.get();
    const keeps = on ? openOn(st, localId(st)).find((x) => !onMap(x.a, s.name, s.detail?.scope || "")) : undefined; // the newest open session on another map
    const line = !on ? r.said || "New sessions run on Auto (the default); a running session keeps its own."
      : (keeps ? s13For(keeps.title, mapName(keeps.a, keeps.plain), s.name) : newSessionsRunOn(s.name)) + tail;
    maps.update(() => ({ inUse: r.in_use, receipt: { line, undo: r.undo_id } }));
    await loadMaps();
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
  }
}

/** [Watch it in Live]: that session in Agents -> 4 · Live (Session's pick too, R1). */
export function watchLive(sid: string): void {
  if (sid) pickLive(sid, true);
  setAgentsView("live");
}

/** The Map's first draw in this page (MapView): from now on a build waits for him to come back, or says so. */
export function markMapDrawn(): void {
  if (mapBuilt.get().drawn) return;
  mapBuilt.update(() => ({ drawn: true }));
  onFilesChanged(["maps", "workflows", "agents"], follow);
  studio.subscribe(arrive);
  agents.subscribe(arrive);
  maps.subscribe(opened);
}
export const setDrafting = (on: boolean): void => { if (mapBuilt.get().drafting !== on) mapBuilt.update(() => ({ drafting: on })); };
export const clearNotice = (): void => mapBuilt.update(() => ({ notice: null }));
const onScreen = () => studio.get().section === "agents" && agents.get().view === "map";

function titleOf(sid: string): string {
  for (const h of fleet.get().harnesses) {
    const row = (h.sessions || []).find((r) => r.session_id === sid);
    if (row) return String(row.title || sid.slice(0, 8));
  }
  return sid.slice(0, 8) || "a session";
}

/** On the Map: the same map with no unsaved edit is re-read in place; anything else is the notice (or, `open`: coming
 *  back with nothing open on it, the map itself). */
function land(n: Notice, open: boolean): void {
  const s = maps.get(), b = mapBuilt.get();
  if (s.name === n.map && !b.drafting) return void rereadDetail(n.map);
  writeLocal(LAST, n.map);
  if (open && !b.drafting && !s.when) return void openMap(n.map);
  mapBuilt.update(() => ({ notice: n }));
}

/** One `builder_done` frame (R25): the last map it wrote. */
export function takeMapBuilt(sid: string, d: Record<string, unknown>, now = Date.now() / 1000): void {
  if (d.outcome !== "applied") return;
  const wrote = (Array.isArray(d.wrote) ? d.wrote : []) as { kind?: string; name?: string; removed?: boolean }[];
  const last = wrote.filter((w) => w && w.kind === "map" && w.name && !w.removed).pop();
  if (!last) return;
  const n: Notice = { map: String(last.name), session: titleOf(sid), t: Number(d.t) || now };
  if (!mapBuilt.get().drawn) return writeLocal(LAST, n.map); // the tab's first draw opens it (firstName)
  if (!onScreen()) {
    writeLocal(LAST, n.map);
    return mapBuilt.update(() => ({ pending: n }));
  }
  land(n, false);
}

function arrive(): void {
  const p = mapBuilt.get().pending;
  if (!p || !onScreen()) return;
  mapBuilt.update(() => ({ pending: null }));
  land(p, true);
}

const ONE: Record<string, string> = { workflows: "workflow", agents: "agent" };

/** 3.6.0.9 V: whether what moved is the open map's file or one its detail bakes in, and differs from what it holds. */
export function moves(name: string, sig: string | undefined, deps: Record<string, string>, c: FilesChange): boolean {
  for (const [k, v] of Object.entries(c.sigs)) {
    const at = k.indexOf(":"), kind = k.slice(0, at), n = k.slice(at + 1);
    if (kind === "maps" ? n === name && v !== sig : !!ONE[kind] && `${ONE[kind]}:${n}` in deps && deps[`${ONE[kind]}:${n}`] !== v) return true;
  }
  return c.removed.some((n) => !!deps[`workflow:${n}`] || !!deps[`agent:${n}`]);
}

function follow(c: FilesChange): void {
  const s = maps.get();
  if (!s.name || !s.detail || !moves(s.name, s.detail.sig, s.detail.deps || {}, c)) return;
  const name = s.name;
  whenDropped(`reread:${name}`, () => void (maps.get().name === name && rereadDetail(name)));
}

let shownName = "";
function opened(): void { // the notice's map opened, by its button or the switcher: the notice is done
  const name = maps.get().name, n = mapBuilt.get().notice;
  if (name !== shownName && n && name === n.map) clearNotice();
  shownName = name;
}

onEvent("builder_done", (f) => takeMapBuilt(f.session_id || "", (f.data || {}) as Record<string, unknown>));
