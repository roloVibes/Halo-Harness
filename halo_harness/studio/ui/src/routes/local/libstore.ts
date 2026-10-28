// Local -> Library's store (3.3.5.0 R2; studio/models_library_api.py): the filters (kept while the tab is open),
// the answer of GET local/library for them, each unfolded model's tags or files (GET local/library/<source>/<id>,
// read once per host and window), and POST local/library/refresh. Every filter change reads the page again; the
// search box waits a moment before it does.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";
import type { LibDetail, LibraryAnswer } from "./types";

export type Filters = {
  q: string; source: "all" | "ollama" | "hf"; host: string; window: number | null; intent: string; fits: boolean;
  family: string; quant: string; cap: string; max_gb: string; license: string;
};
type Lib = { filters: Filters; data: LibraryAnswer | null; loading: boolean; error: string; details: Record<string, LibDetail | "loading" | string> };

export const NO_FILTERS: Filters = { q: "", source: "all", host: "", window: null, intent: "", fits: false, family: "", quant: "", cap: "", max_gb: "", license: "" };
export const lib = createStore<Lib>({ filters: NO_FILTERS, data: null, loading: false, error: "", details: {} });
export const WINDOWS = [4096, 8192, 16384, 32768, 65536, 131072, 262144];

export function useLib<S>(select: (s: Lib) => S): S {
  return useStore(lib, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
let seq = 0;

function query(f: Filters): Record<string, string | number> {
  const q: Record<string, string | number> = { source: f.source };
  for (const k of ["q", "host", "intent", "family", "quant", "cap", "max_gb", "license"] as const) if (f[k]) q[k] = f[k];
  if (f.window) q.window = f.window;
  if (f.fits) q.fits = 1;
  return q;
}

export async function loadLibrary(): Promise<void> {
  const n = ++seq;
  lib.update(() => ({ loading: true }));
  try {
    const data = await api.get<LibraryAnswer>("local/library", query(lib.get().filters));
    if (n === seq) lib.update(() => ({ data, loading: false, error: "" }));
  } catch (e) {
    if (n === seq) lib.update(() => ({ loading: false, error: msg(e) }));
  }
}

let timer: ReturnType<typeof setTimeout> | null = null;

/** Change filters and read the list again (a typed search waits 300 ms for the next key). */
export function setFilters(patch: Partial<Filters>, wait = false): void {
  lib.update((s) => ({ filters: { ...s.filters, ...patch }, details: {} }));
  if (timer) clearTimeout(timer);
  if (wait) timer = setTimeout(() => void loadLibrary(), 300);
  else void loadLibrary();
}

export function detailKey(source: string, id: string): string {
  const f = lib.get().filters;
  return `${source}/${id}|${f.host}|${f.window || ""}`;
}

export async function loadDetail(source: string, id: string): Promise<void> {
  const key = detailKey(source, id);
  if (lib.get().details[key]) return;
  lib.update((s) => ({ details: { ...s.details, [key]: "loading" } }));
  const f = lib.get().filters;
  const q: Record<string, string | number> = {};
  if (f.host) q.host = f.host;
  if (f.window) q.window = f.window;
  try {
    const d = await api.get<LibDetail>(`local/library/${source}/${id.split("/").map(encodeURIComponent).join("/")}`, q);
    lib.update((s) => ({ details: { ...s.details, [key]: d } }));
  } catch (e) {
    lib.update((s) => ({ details: { ...s.details, [key]: msg(e) } }));
  }
}

export async function refreshLibrary(): Promise<void> {
  try {
    await api.post("local/library/refresh", {});
  } catch {
    /* the read below says what the sites answer */
  }
  lib.update(() => ({ details: {} }));
  await loadLibrary();
}

/** The pull line on the clipboard; the answer is said on the button (a page without a clipboard: "copy it by hand"). */
export async function copyLine(line: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(line);
    return true;
  } catch {
    return false;
  }
}

export function gb(n: number | null | undefined): string {
  if (typeof n !== "number" || n <= 0) return "?";
  return n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${Math.round(n / 1e6)} MB`;
}

export function count(n: number | null | undefined): string {
  if (typeof n !== "number") return "";
  return n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n);
}
