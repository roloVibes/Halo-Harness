// The bundle panel's `api` (3.2.0.0 R3: pack, panel, get, config; 3.3.10.0 R3: the calls that act):
// what PackBundle hands a pack's own module in `mount(el, api)`. Every call below is the pack's own: its files,
// its data folder, its declared event kinds and attention rows, its mode (and `lib`'s client is scoped to the pack's
// own routes, 3.3.14.0 R1: packlib/scoped.ts); the routes behind them answer 403
// naming the grant until studio-script is granted (studio/packs_studio_bundle_api.py), and the module itself
// loads only then. docs/EXTENSION_API.md "Studio contributions" has the table.
//
//   publish(kind, data)      -> Promise<{ok, kind, published, problems?}>  POST pack/<id>/publish; rejects with the
//                               server's line (an undeclared kind, a bad name: 422; past the rate: 429)
//   on(kind, cb)             -> off()   cb({kind, data, ts, problems?}) for each of the pack's own frames of kind
//   getData(path)            -> Promise<string>  a file of the pack's data folder, read-only (GET pack/<id>/data/...)
//   mode()                   -> Promise<{mode, label, since, by, armed, modes}>  GET pack/<id>/mode
//   attention({row, kind, what, detail?}) -> Promise<{ok, row, kind, file}>  POST pack/<id>/attention: one row of
//                               the Fleet attention queue, the pack named, answered through the answers contract
//   route(section, panel?)   -> boolean  Studio goes to a core section or one of the pack's own (and focuses the
//                               panel), with the shell's own goSection / focusPanel; false when it names neither
// 3.3.13.0 R2 (API 1.2): `lib` (packlib/index.ts: the shell's React, ReactDOM, lib/ui and helpers), `routes` (the
// path of the pack's own routes under /api/, "" without them), `section` (the section the module draws in); `on`
// hears the pack's `pack_live` frames (its routes' ctx.publish) as well as its `pack_event` ones.
import { api as http, ApiError } from "../../lib/api";
import { onEvent, type FeedFrame } from "../../lib/events";
import { SECTION_IDS, type CoreSectionId } from "../../lib/store";
import { libFor, type StudioLib } from "../../packlib";
import { packKey } from "./importPack";
import { fetchText, openRoute } from "./nav";
import { packs, packSectionIds } from "./store";
import type { PackPanel } from "./types";

export type BundleFrame = { kind: string; data: unknown; ts: number; problems?: string[] };
export type Published = { ok: boolean; kind: string; published: boolean; problems?: string[] };
export type ModeState = { pack: string; mode: string | null; label: string | null; since: string | null; by: string | null;
  armed: string[]; modes: { id: string; label: string }[] };
export type AttentionRow = { row: string; kind: string; what: string; detail?: string };
export type Attention = { ok: boolean; row: string; kind: string; file: string };

export type BundleApi = {
  pack: string;
  panel: string;
  get: (path: string) => Promise<string>;
  config: () => Promise<unknown>;
  publish: (kind: string, data?: unknown) => Promise<Published>;
  on: (kind: string, cb: (f: BundleFrame) => void) => () => void;
  getData: (path: string) => Promise<string>;
  mode: () => Promise<ModeState>;
  attention: (row: AttentionRow) => Promise<Attention>;
  route: (section: string, panel?: string) => boolean;
  lib: StudioLib;
  routes: string;
  section: string;
};

/** The server's own line as the Error a bundle catches (ApiError keeps status and problems). */
function plain<T>(p: Promise<T>): Promise<T> {
  return p.catch((e: unknown) => {
    throw e instanceof ApiError ? Object.assign(new Error(e.message), { status: e.status, problems: e.problems }) : e;
  });
}

const sep = "--";
const own = (pack: string, id: string) => (id.includes(sep) ? id : `${pack}${sep}${id}`);

/** Where route(section, panel) goes: a core section as it is, a pack section only when it is this pack's own. */
export function routeOf(pack: string, section: string, panel?: string): { section: string; panel?: string } | null {
  if (typeof section !== "string" || !section) return null;
  if ((SECTION_IDS as string[]).includes(section)) return { section: section as CoreSectionId, ...(panel ? { panel } : {}) };
  const sec = own(pack, section);
  if (!sec.startsWith(pack + sep) || !packSectionIds().includes(sec)) return null;
  return { section: sec, ...(panel ? { panel: own(pack, panel) } : {}) };
}

/** The api for one bundle panel, and `close()`: every `on` it made stops (PackBundle calls it on unmount). */
export function bundleApi(p: PackPanel): { api: BundleApi; close: () => void } {
  const base = `pack/${p.pack}`;
  const offs = new Set<() => void>();
  const on = (kind: string, cb: (f: BundleFrame) => void) => {
    const hear = (f: FeedFrame) => {
      const d = (f.data || {}) as { pack?: unknown; kind?: unknown; data?: unknown; problems?: unknown };
      if (d.pack !== p.pack || d.kind !== kind) return;
      const frame: BundleFrame = { kind, data: d.data ?? null, ts: Number(f.ts) || Date.now() / 1000 };
      if (Array.isArray(d.problems) && d.problems.length) frame.problems = d.problems.map(String);
      try {
        cb(frame);
      } catch (e) {
        console.error(`${p.pack}: an on(${kind}) callback threw`, e);
      }
    };
    const stops = [onEvent("pack_event", hear), onEvent("pack_live", hear)]; // pack_live: 3.3.13.0 R2
    const off = () => {
      stops.forEach((stop) => stop());
      offs.delete(off);
    };
    offs.add(off);
    return off;
  };
  const api: BundleApi = {
    pack: p.pack,
    panel: p.name,
    get: (path) => fetchText(`api/${base}/file/${path}`),
    config: () => http.get(`${base}/config`),
    publish: (kind, data = null) => plain(http.post<Published>(`${base}/publish`, { kind, data })),
    on,
    getData: (path) => fetchText(`api/${base}/data/${path}`),
    mode: () => plain(http.get<ModeState>(`${base}/mode`)),
    attention: (row) => plain(http.post<Attention>(`${base}/attention`, row)),
    route: (section, panel) => {
      const r = routeOf(p.pack, section, panel);
      if (r) openRoute(r);
      return !!r;
    },
    lib: libFor(p.pack, packKey(p.pack)),
    routes: packs.get().reg.packs.find((x) => x.id === p.pack)?.routes?.api.replace(/^api\//, "") || "",
    section: p.section,
  };
  return { api, close: () => [...offs].forEach((off) => off()) };
}
