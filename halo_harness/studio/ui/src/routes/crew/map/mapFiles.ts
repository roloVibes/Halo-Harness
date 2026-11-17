// The maps a run's drawing shows, by version (3.6.0.2 R26 R27 R28 R50), shared by Session's Live drawer and Agents' Live
// view (no Session import). A map is cached `{name}@{version}`: the version is the applied outcome's undo id (a Builder
// card's `builder_done`) or the tick of the `files_changed` frame that named it; never the file's mtime, never the name
// alone (a same-name edit would never redraw). Nothing waits on it: a body the frame brought is drawn at once (its boxes'
// facts kept from the version before when the box is unchanged); the one read a map needs is made after the first draw,
// by scope and path when the row names the file, always soft (200 `{removed}` / `{unreadable}`, never a failed /api).
// A `files_changed` only moves the version (it re-reads nothing by itself): the drawing open now reads its new version;
// a closed one reads it when it is opened. It never marks anything new.
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { onEvent } from "../../../lib/events";
import type { MapDetail, MapFile } from "./mapTypes";

/** Where the file is (the status row's `map_scope` / `map_path`); empty: the name in the stores' order. */
export type Where = { scope?: string | null; path?: string | null };
/** A map as drawn: its detail (`thin`: a workflow box's steps are not known yet), gone at `removed`, or not readable. */
export type Got = { detail: MapDetail; thin?: boolean } | { removed: number } | { unreadable: true };

const ver = new Map<string, string>();
const got = new Map<string, Got>();
const asked = new Set<string>();
const subs = new Set<() => void>();
let tick = 0;
const changed = () => subs.forEach((f) => f());

export const keyOf = (name: string): string => `${name}@${ver.get(name) || "0"}`;

/** The newest version of `name` the page has (the current one, else the last one read before it). */
function latest(name: string): Got | undefined {
  const g = got.get(keyOf(name));
  if (g) return g;
  for (const [k, v] of [...got.entries()].reverse()) if (k.startsWith(`${name}@`)) return v;
  return undefined;
}

/** The map's file as the page has it last, for a build's diff; null when it has none. */
export function current(name: string): MapFile | null {
  const g = latest(name);
  return g && "detail" in g ? g.detail.map : null;
}

/** R27: a version moved without a body (a body over 64 KB left out of the frame). */
export function bump(name: string, v: string): void {
  ver.set(name, v);
  changed();
}

/** R28: a body a `builder_done` frame brought, version `v`; `stale`: workflows the build wrote (their boxes' steps are
 *  read again). Boxes unchanged since the version before keep their facts; a workflow box without them makes it thin. */
export function putBody(name: string, v: string, map: MapFile, stale: string[]): void {
  const was = latest(name);
  const prev = was && "detail" in was ? was.detail : null;
  const boxes: MapDetail["boxes"] = {};
  let thin = false;
  for (const b of map.boxes || []) {
    const old = prev?.map.boxes.find((x) => x.id === b.id);
    if (prev?.boxes[b.id] && old && JSON.stringify(old) === JSON.stringify(b) && !(b.workflow && stale.includes(b.workflow))) boxes[b.id] = prev.boxes[b.id];
    else if (b.workflow) thin = true;
  }
  const detail = { scope: "yours", writable: false, in_use: false, problems: [], main: { agent: map.main?.agent || "main" }, ...prev, map, boxes } as MapDetail;
  ver.set(name, v);
  got.set(keyOf(name), { detail, thin });
  changed();
}

/** R26: names a `files_changed` frame wrote or removed: their version moves (a new tick); nothing is marked. */
function filesTick(names: string[]): void {
  if (!names.length) return;
  tick += 1;
  for (const n of names) ver.set(n, `f${tick}`);
  changed();
}

let bound = false;
function bind(): void {
  if (bound) return;
  bound = true;
  onEvent("files_changed", (f) => {
    const d = (f.data || {}) as Record<string, unknown>;
    if (d.kind !== "maps") return;
    const strs = (v: unknown) => (Array.isArray(v) ? v.map(String) : []);
    filesTick([...strs(d.names), ...strs(d.removed)]);
  });
}

/** R28 R50: the one read of a version, soft; an answer that failed is forgotten (read again on the next draw). */
function read(name: string, where: Where): void {
  const key = keyOf(name);
  if (asked.has(key)) return;
  asked.add(key);
  const q = [where.scope ? `scope=${encodeURIComponent(where.scope)}` : "", where.path ? `path=${encodeURIComponent(where.path)}` : "", "soft=1"];
  void api.get<MapDetail & { removed?: boolean; unreadable?: boolean }>(`crew/map/${encodeURIComponent(name)}?${q.filter(Boolean).join("&")}`).then(
    (d) => (got.set(key, d.removed ? { removed: Date.now() / 1000 } : d.unreadable ? { unreadable: true } : { detail: d }), changed()),
    () => asked.delete(key));
}

/** The map `name` as it is drawn now (null while its first version is read), read after the draw when `on` and the
 *  page does not have it (or has it thin). `where` is used for the file the row names. */
export function useMapFile(name: string, where: Where, on = true): Got | null {
  const [, setN] = useState(0);
  useEffect(() => {
    bind();
    const f = () => setN((n) => n + 1);
    subs.add(f);
    return () => void subs.delete(f);
  }, []);
  const key = name ? keyOf(name) : "";
  const g = key ? got.get(key) : undefined;
  const need = on && !!name && (!g || ("thin" in g && !!g.thin));
  useEffect(() => {
    if (need) read(name, where);
  }, [key, need]); // eslint-disable-line react-hooks/exhaustive-deps
  return (name && latest(name)) || null; // a newer version not read yet: the one before stays drawn until it lands
}
