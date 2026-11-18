// The Map tab's store (3.6.0.0 R3; docs/STUDIO-map.md): the maps (GET crew/maps), the open one (GET crew/map/<name>),
// every change the page makes -- add a box, connect, a line's When, take a line out, + New map -- saved at once (PUT
// crew/map/<name>, the before-image kept), then a receipt line with Undo (POST builder/undo: the builder's own store).
// "New sessions run on this" is POST crew/map/<name>/use (mapSwitch.ts). Lock (off by default, kept in this browser) stops every change;
// 3.6.0.5 A11: so does a read-only map (Auto: `locked` = his Lock or readOnly, autoWords.ts).
// The builder box on this tab says which map is open and reloads it after an Apply or an Undo (builderStore onTab).
import { api, ApiError } from "../../../lib/api";
import { onFilesChanged } from "../../../lib/filesLive";
import { createStore, useStore, writeLocal } from "../../../lib/store";
import { loadCrew } from "../store";
import { loadFlows } from "../flows/flowStore";
import { onTab } from "../builderStore";
import type { LineWhen, MapDetail, MapFile, MapLine, MapRow } from "./mapTypes";
import { nameOfTheDefault, openName } from "./truthWords";
import { readOnly } from "./autoWords";
import { mapUrl } from "./pickerRows";

export type WhenAt = { from: string; to: string; fresh: boolean; before?: MapFile };
export type MapState = {
  rows: MapRow[];
  listed: boolean; // GET crew/maps answered (or failed): `rows` is what there is
  inUse: string | null;
  /** 3.6.0.2 R24 (F4): the map new sessions use -- the API's `next` (config crew.map), null when unset */
  next: string | null;
  /** P7: new sessions start with NO map (roles off, crew.map unset) -- the API's `next_none`, the truth block's field */
  nextNone: boolean;
  name: string;
  /** 3.6.0.5 A5: the scope the open map was opened by -- "" except while his own old file (auto/starter) is open */
  scope: string;
  detail: MapDetail | null;
  /** his Lock (kept in this browser; toggleLock) */
  handLock: boolean;
  /** nothing can be added, connected or saved: his Lock, or a read-only map (3.6.0.5 A11: Auto) */
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
export const LAST = "halo.studio.map-open";
const read = (k: string) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };

export const maps = createStore<MapState>({ rows: [], listed: false, inUse: null, next: null, nextNone: false, name: "", scope: "", detail: null, handLock: read(LOCK) === "1", locked: read(LOCK) === "1", open: {}, hover: "",
  pick: "", when: null, receipt: null, error: "", made: [] });
export const useMap = <T,>(pick: (s: MapState) => T): T => useStore(maps, pick);
export const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

let watching = false;

export async function loadMaps(): Promise<void> {
  if (!watching) {  // 3.6.0.0 R5b: a map file (or config's crew.map) changed outside Studio shows at once
    watching = true;
    onFilesChanged(["maps", "config"], () => void loadMaps());
  }
  try {
    const r = await api.get<{ maps: MapRow[]; in_use: string | null; next?: string | null; next_none?: boolean }>("crew/maps");
    maps.update(() => ({ rows: r.maps, inUse: r.in_use, next: r.next || null, nextNone: !r.next && r.next_none === true, listed: true }));
  } catch (e) {
    maps.update(() => ({ error: msg(e), listed: true }));
  }
}

/** The map a link names (`&map=`), else the one opened last here, else this project's, else the one in use, else Auto. */
export function firstName(): string {
  const s = maps.get();
  let url = "";
  try { url = new URLSearchParams(location.search).get("map") || ""; } catch { /* no URL */ }
  const has = (n: string) => !!n && s.rows.some((r) => r.name === n);
  return [url, read(LAST), s.rows.find((r) => r.scope === "project")?.name || "", s.inUse || "", "auto"].find(has) || s.rows[0]?.name || "";
}

export { openName, readOnly }; // 3.6.0.5: the name a map is opened under (truthWords.ts), a read-only map (autoWords.ts)
export { mapUrl, pickerValue } from "./pickerRows"; // 3.6.0.5 A5: a map's address and switcher value by its scope

let opening = 0; // the latest openMap: an earlier one answered late (the tab's own first open) never undoes his pick

/** Open a map; A5: `scope` opens his own old file named auto or starter by its scope (never remembered as LAST). */
export async function openMap(asked: string, scope = ""): Promise<void> {
  if (!asked) return;
  const name = openName(asked, scope);
  if (!scope) writeLocal(LAST, name); // 3.6.0.0 R5: first, so the tab's own first load (firstName) opens this one too (an edit door)
  const mine = ++opening;
  try {
    const detail = await api.get<MapDetail>(mapUrl(name, scope));
    if (mine === opening) maps.update((s) => ({ name, scope, detail, error: "", pick: "", when: null, open: s.name === name ? s.open : {},
                                                 locked: s.handLock || readOnly(name, detail.scope) }));
  } catch (e) {
    if (mine === opening) maps.update(() => ({ error: msg(e) }));
  }
}

/** 3.6.0.2 R33: the open map changed by a session's build -- its detail re-read in place, keeping the pick, the When
 *  card, the open boxes and the receipt (a real change of map is openMap's, which resets them). A5: by the scope it
 *  was opened with, so a re-read never puts Auto's detail in place of his old file's. */
export async function rereadDetail(name: string): Promise<void> {
  try {
    const s = maps.get();
    const detail = await api.get<MapDetail>(mapUrl(name, s.name === name ? s.scope : ""));
    if (maps.get().name === name) maps.update(() => ({ detail }));
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
    await Promise.all([openMap(maps.get().name, maps.get().scope), loadMaps()]);
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
  if (/^(auto|starter)$/i.test(name.trim())) { // A6 (W16): never a map of his under a default's name; no request
    maps.update(() => ({ error: nameOfTheDefault(name.trim()) }));
    return false;
  }
  const n = name.trim().toLowerCase();
  if (!/^[a-z][a-z0-9-]{0,47}$/.test(n) || maps.get().rows.some((r) => r.name === n)) {
    maps.update(() => ({ error: `A new map needs a name of its own: lowercase letters, digits and dashes (${n || "empty"}).` }));
    return false;
  }
  try {
    const r = await api.put<MapDetail & { undo_id: string }>(`crew/map/${n}`, { map: { name: n, boxes: [], lines: [], main: { agent: "main" } } });
    maps.update((s) => ({ name: n, scope: "", detail: r, receipt: { line: `Made the map ${n}: main only so far.`, undo: r.undo_id }, open: {},
                          locked: s.handLock || readOnly(n, r.scope) }));
    writeLocal(LAST, n);
    await loadMaps();
    return true;
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
    return false;
  }
}

export function toggleLock(): void {
  const handLock = !maps.get().handLock;
  writeLocal(LOCK, handLock ? "1" : "0");
  maps.update((s) => ({ handLock, locked: handLock || readOnly(s.name, s.detail?.scope || ""), pick: "", when: null }));
}

export const toggleOpen = (id: string) => maps.update((s) => ({ open: { ...s.open, [id]: !s.open[id] } }));
export const setHover = (id: string) => maps.update((s) => (s.hover === id ? {} : { hover: id }));
export const setPick = (id: string) => maps.update((s) => ({ pick: s.pick === id ? "" : id, when: null }));
export const dismissError = () => maps.update(() => ({ error: "" }));

onTab("map", {
  selection: () => ({ map: maps.get().name }),
  after: async () => { await Promise.all([openMap(maps.get().name, maps.get().scope), loadMaps(), loadCrew(), loadFlows()]); },
  show: async () => undefined,
});
