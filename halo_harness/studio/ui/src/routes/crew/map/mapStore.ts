// The Map tab's store (3.6.0.0 R3; docs/STUDIO-map.md): the maps (GET crew/maps), the open one (GET crew/map/<name>),
// every change the page makes -- add a box, connect, a line's When, take a line out, + New map -- saved at once (PUT
// crew/map/<name>, the before-image kept), then a receipt line with Undo (POST builder/undo: the builder's own store).
// "My sessions use this" is POST crew/map/<name>/use. Lock (off by default, kept in this browser) stops every change.
// The builder box on this tab says which map is open and reloads it after an Apply or an Undo (builderStore onTab).
import { api, ApiError } from "../../../lib/api";
import { onFilesChanged } from "../../../lib/filesLive";
import { createStore, useStore, writeLocal } from "../../../lib/store";
import { loadCrew } from "../store";
import { loadFlows } from "../flows/flowStore";
import { onTab } from "../builderStore";
import type { LineWhen, MapDetail, MapFile, MapLine, MapRow } from "./mapTypes";

export type WhenAt = { from: string; to: string; fresh: boolean; before?: MapFile };
export type MapState = {
  rows: MapRow[];
  inUse: string | null;
  name: string;
  detail: MapDetail | null;
  locked: boolean;
  open: Record<string, boolean>;
  hover: string;
  pick: string;
  when: WhenAt | null;
  receipt: { line: string; undo: string } | null;
  error: string;
  made: string[];
};

const LOCK = "halo.studio.map-lock";
const LAST = "halo.studio.map-open";
const read = (k: string) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };

export const maps = createStore<MapState>({ rows: [], inUse: null, name: "", detail: null, locked: read(LOCK) === "1", open: {}, hover: "",
  pick: "", when: null, receipt: null, error: "", made: [] });
export const useMap = <T,>(pick: (s: MapState) => T): T => useStore(maps, pick);
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

let watching = false;

export async function loadMaps(): Promise<void> {
  if (!watching) {  // 3.6.0.0 R5b: a map file (or config's crew.map) changed outside Studio shows at once
    watching = true;
    onFilesChanged(["maps", "config"], () => void loadMaps());
  }
  try {
    const r = await api.get<{ maps: MapRow[]; in_use: string | null }>("crew/maps");
    maps.update(() => ({ rows: r.maps, inUse: r.in_use }));
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
  }
}

/** The map a link names (`&map=`), else the one opened last here, else this project's, else the one in use, else starter. */
export function firstName(): string {
  const s = maps.get();
  let url = "";
  try { url = new URLSearchParams(location.search).get("map") || ""; } catch { /* no URL */ }
  const has = (n: string) => !!n && s.rows.some((r) => r.name === n);
  return [url, read(LAST), s.rows.find((r) => r.scope === "project")?.name || "", s.inUse || "", "starter"].find(has) || s.rows[0]?.name || "";
}

export async function openMap(name: string): Promise<void> {
  if (!name) return;
  writeLocal(LAST, name); // 3.6.0.0 R5: first, so the tab's own first load (firstName) opens this one too (an edit door)
  try {
    const detail = await api.get<MapDetail>(`crew/map/${name}`);
    maps.update((s) => ({ name, detail, error: "", pick: "", when: null, open: s.name === name ? s.open : {} }));
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
  }
}

export const mapFile = (): MapFile | null => maps.get().detail?.map || null;

/** Save the map as it now is; the receipt line says what changed and offers Undo. False when it was refused. */
export async function save(next: MapFile, line: string): Promise<boolean> {
  const s = maps.get();
  if (s.locked || !s.name) return false;
  try {
    const r = await api.put<MapDetail & { undo_id: string }>(`crew/map/${s.name}`, { map: next });
    maps.update(() => ({ detail: r, receipt: { line, undo: r.undo_id }, error: "" }));
    void loadMaps();
    return true;
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
    return false;
  }
}

export async function undoLast(): Promise<void> {
  const r = maps.get().receipt;
  if (!r) return;
  try {
    await api.post("builder/undo", { undo_id: r.undo });
    maps.update(() => ({ receipt: null }));
    await Promise.all([openMap(maps.get().name), loadMaps()]);
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
  }
}

const freeId = (m: MapFile, ref: string) => {
  const ids = new Set(["main", ...m.boxes.map((b) => b.id)]);
  if (!ids.has(ref)) return ref;
  for (let i = 2; ; i++) if (!ids.has(`${ref}-${i}`)) return `${ref}-${i}`;
};

/** Add a box: under "Not connected yet", or (`onto`) with a line from that box whose When card opens at once. */
export async function addBox(kind: "agent" | "workflow", ref: string, onto?: string): Promise<void> {
  const m = mapFile();
  if (!m || maps.get().locked) return;
  const id = freeId(m, ref);
  const next: MapFile = { ...m, boxes: [...m.boxes, { id, [kind]: ref }], lines: onto ? [...m.lines, { from: onto, to: id, when: "main-decides" }] : m.lines };
  const who = onto === "main" ? "main" : onto;
  const ok = await save(next, onto ? `${who} hands work to ${ref} (main decides per task). Pick its When on the card.`
    : `Added ${ref} to "Not connected yet" on ${m.name}: nothing hands it work until you connect it.`);
  if (ok) maps.update((s) => ({ made: [...s.made, id], when: onto ? { from: onto, to: id, fresh: true, before: m } : null }));
}

/** A line from `from` to `to` (a strip box's dot dragged onto a box: that box hands work to it). */
export async function connect(from: string, to: string): Promise<void> {
  const m = mapFile();
  if (!m || maps.get().locked || from === to || to === "main") return;
  if (m.lines.some((l) => l.from === from && l.to === to)) return openWhen(from, to, false);
  const next = { ...m, lines: [...m.lines, { from, to, when: "main-decides" as LineWhen }] };
  if (await save(next, `${from} hands work to ${to} (main decides per task). Pick its When on the card.`))
    maps.update(() => ({ when: { from, to, fresh: true, before: m } }));
}

export const openWhen = (from: string, to: string, fresh: boolean) => maps.update(() => ({ when: { from, to, fresh }, pick: "" }));
export const closeWhen = () => maps.update(() => ({ when: null }));

export async function setWhen(from: string, to: string, when: LineWhen, words: string): Promise<void> {
  const m = mapFile();
  if (!m) return;
  const lines = m.lines.map((l) => (l.from === from && l.to === to ? { ...l, when } : l));
  if (await save({ ...m, lines }, `${from} hands work to ${to}: ${words}.`)) closeWhen();
}

export async function removeLine(l: MapLine): Promise<void> {
  const m = mapFile();
  if (!m) return;
  if (await save({ ...m, lines: m.lines.filter((x) => !(x.from === l.from && x.to === l.to)) }, `Took out the line ${l.from} -> ${l.to}; ${l.to} waits under "Not connected yet".`))
    closeWhen();
}

export async function newMap(name: string): Promise<boolean> {
  const n = name.trim().toLowerCase();
  if (!/^[a-z][a-z0-9-]{0,47}$/.test(n) || maps.get().rows.some((r) => r.name === n)) {
    maps.update(() => ({ error: `A new map needs a name of its own: lowercase letters, digits and dashes (${n || "empty"}).` }));
    return false;
  }
  try {
    const r = await api.put<MapDetail & { undo_id: string }>(`crew/map/${n}`, { map: { name: n, boxes: [], lines: [], main: { agent: "main" } } });
    maps.update(() => ({ name: n, detail: r, receipt: { line: `Made the map ${n}: main only so far.`, undo: r.undo_id }, open: {} }));
    writeLocal(LAST, n);
    await loadMaps();
    return true;
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
    return false;
  }
}

export async function setUse(on: boolean): Promise<void> {
  const s = maps.get();
  try {
    const r = await api.post<{ undo_id: string; in_use: string | null }>(`crew/map/${s.name}/use`, { on });
    maps.update(() => ({ inUse: r.in_use, receipt: { line: on ? `New sessions run on ${s.name}; a running session keeps its own.`
      : "New sessions run on no map (as before maps).", undo: r.undo_id } }));
    await loadMaps();
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
  }
}

export function toggleLock(): void {
  const locked = !maps.get().locked;
  writeLocal(LOCK, locked ? "1" : "0");
  maps.update(() => ({ locked, pick: "", when: null }));
}

export const toggleOpen = (id: string) => maps.update((s) => ({ open: { ...s.open, [id]: !s.open[id] } }));
export const setHover = (id: string) => maps.update((s) => (s.hover === id ? {} : { hover: id }));
export const setPick = (id: string) => maps.update((s) => ({ pick: s.pick === id ? "" : id, when: null }));
export const dismissError = () => maps.update(() => ({ error: "" }));

onTab("map", {
  selection: () => ({ map: maps.get().name }),
  after: async () => { await Promise.all([openMap(maps.get().name), loadMaps(), loadCrew(), loadFlows()]); },
  show: async () => undefined,
});
