// The Pack Manager's store (3.2.0.0 R6, the Packs section): `GET pack/manager`
// read once and again on every `pack_changed` frame (an install, a grant, an
// enable, a disable, an update, a remove, a source added -- from this page,
// another Studio or a `halo pack` in a terminal), the selected pack, the
// grants picked for a disabled pack's Enable, and the last action's lines
// (the CLI's own words). Every action posts to the route `halo pack` mirrors
// (studio/packs_manager_api.py) and the page redraws from the frame.
import { api, ApiError } from "../../../lib/api";
import { onEvent } from "../../../lib/events";
import { createStore, setSectionStatus, toast, useStore } from "../../../lib/store";
import type { Done, Manager, PackRow, UpdatePreview } from "./types";

export type MgrState = {
  data: Manager | null;
  loaded: boolean;
  error: string;
  /** The selected pack's id (Details, Settings and Templates follow it). */
  sel: string;
  busy: string;
  /** A disabled pack's Grant toggles: what its Enable grants. */
  picks: Record<string, string[]>;
  last: Done | null;
  /** The Remove confirm, open for this pack id. */
  removing: string;
  /** 3.2.0.0 R7: the Update confirm, with what the dry run said (the migration notes first). */
  updating: UpdatePreview | null;
};

export const mgr = createStore<MgrState>({ data: null, loaded: false, error: "", sel: "", busy: "", picks: {}, last: null, removing: "", updating: null });

export function useMgr<S>(select: (s: MgrState) => S): S {
  return useStore(mgr, select);
}

let started = false;
let loading: Promise<void> | null = null;

/** The selected pack: an installed one, else a source pack's details (not installed yet). */
export function selected(s: MgrState = mgr.get()): PackRow | null {
  const d = s.data;
  if (!d || !s.sel) return null;
  const own = d.packs.find((p) => p.id === s.sel);
  if (own) return own;
  for (const src of d.sources) for (const p of src.packs) if (p.id === s.sel && p.details && !p.installed) return p.details;
  return null;
}

function status(d: Manager): void {
  const on = d.packs.filter((p) => p.running).length;
  const warn = d.packs.reduce((n, p) => n + p.health.length, 0);
  setSectionStatus("packs", `${d.packs.length} installed · ${on} running${warn ? ` · ${warn} doctor line${warn === 1 ? "" : "s"}` : ""}`);
}

export async function loadManager(): Promise<void> {
  if (loading) return loading;
  loading = (async () => {
    try {
      const data = await api.get<Manager>("pack/manager");
      mgr.update((s) => ({ data, loaded: true, error: "", sel: s.sel || data.packs[0]?.id || "" }));
      status(data);
    } catch (e) {
      mgr.update(() => ({ loaded: true, error: e instanceof Error ? e.message : String(e) }));
    } finally {
      loading = null;
    }
  })();
  return loading;
}

/** Start once (the section's panels): the first read and the `pack_changed` handler. */
export function startManager(): void {
  if (started) return;
  started = true;
  onEvent("pack_changed", () => void loadManager());
  void loadManager();
}

export function selectPack(id: string): void {
  mgr.update(() => ({ sel: id }));
}

export function togglePick(id: string, need: string, on: boolean): void {
  mgr.update((s) => {
    const have = new Set(s.picks[id] || []);
    if (on) have.add(need);
    else have.delete(need);
    return { picks: { ...s.picks, [id]: [...have] } };
  });
}

/** POST one action; the CLI's lines land in `last` (and a toast), the frame redraws the page. */
export async function act(path: string, body: Record<string, unknown>, what: string): Promise<boolean> {
  mgr.update(() => ({ busy: what }));
  try {
    const r = await api.post<{ ok: boolean; lines: string[]; id?: string }>(path, body);
    mgr.update((s) => ({ last: { ok: true, lines: r.lines || [], what }, sel: r.id || s.sel }));
    toast(r.lines?.[0] || `${what}: done`, "done", 4000);
    await loadManager();
    return true;
  } catch (e) {
    const lines = e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)];
    mgr.update(() => ({ last: { ok: false, lines, what } }));
    toast(`${what}: ${lines[0]}`, "error", 6000);
    return false;
  } finally {
    mgr.update(() => ({ busy: "" }));
  }
}

const grantArgs = (names: string[]) => names.map((n) => ` --grant ${n}`).join("");

/** The command line each action is (its button's title): the same verb in a terminal. */
export const cli = {
  enable: (id: string, names: string[]) => `halo pack enable ${id}${grantArgs(names)}`,
  disable: (id: string) => `halo pack disable ${id}`,
  update: (id: string, dry = false) => `halo pack update ${id}${dry ? " --dry-run" : ""}`,
  rollback: (id: string) => `halo pack rollback ${id}`,
  remove: (id: string, keep: boolean) => `halo pack remove ${id}${keep ? " --keep-config" : ""}`,
  install: (id: string, project: boolean) => `halo pack install ${id}${project ? " --project" : ""}`,
  grant: (id: string, need: string, on: boolean) => `halo pack grant ${id} ${need}${on ? "" : " --off"}`,
};

export const enablePack = (id: string, names: string[]) => act(`pack/${id}/enable`, { grants: names }, `Enable ${id}`);
export const disablePack = (id: string) => act(`pack/${id}/disable`, {}, `Disable ${id}`);
export const updatePack = (id: string) => act(`pack/${id}/update`, {}, `Update ${id}`);
export const rollbackPack = (id: string) => act(`pack/${id}/rollback`, {}, `Roll back ${id}`);

/** 3.2.0.0 R7: Update asks first -- the dry run's lines (its migration notes, what changes) in a confirm. */
export async function previewUpdate(id: string): Promise<void> {
  mgr.update(() => ({ busy: `Update ${id}` }));
  try {
    const r = await api.post<{ ok: boolean; lines: string[] }>(`pack/${id}/update`, { dry_run: true });
    mgr.update(() => ({ updating: { id, ok: true, lines: r.lines || [] } }));
  } catch (e) {
    const lines = e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)];
    mgr.update(() => ({ updating: { id, ok: false, lines } }));
  } finally {
    mgr.update(() => ({ busy: "" }));
  }
}
export const removePack = (id: string, keep: boolean) => act(`pack/${id}/remove`, { keep_config: keep }, `Remove ${id}`);
export const grantPack = (id: string, need: string, on: boolean) => act(`pack/${id}/grant`, { need, on }, `${on ? "Grant" : "Take back"} ${need}`);
export const installPack = (source: string, project: boolean, id: string) => act("pack/install", { source, project }, `Install ${id}`);
export const addSource = (source: string) => act("pack/sources", { add: source }, "Add source");
export const removeSource = (source: string) => act("pack/sources", { remove: source }, "Remove source");
