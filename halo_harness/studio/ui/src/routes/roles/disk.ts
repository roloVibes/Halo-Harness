// Roles follows the disk (3.2.2.0 R6, "I asked to update the roles but I had
// to refresh"): the `files_changed` frames (studio/files_live.py, through
// lib/filesLive.ts) re-read what moved. `lineups`: the lineup list, and the
// open lineup (graph, canvas, inspector) when its file is named; `bios`: the
// Bios panel, the inspector's bio choices, the open bio, the cards' models;
// `layouts`: the open lineup's card positions and tier boxes (unless a move
// of yours is still on its way to the file); `config`: the active lineup
// mark, roles on/off, the default model. Studio's own writes come back too
// and change nothing: what the file holds is compared with what the page
// holds. An unsaved draft (the lineup's mapping, the bio form, a field being
// typed in) is never overwritten: the page says "<name> changed on disk"
// with Reload / Keep mine (DiskNote.tsx). A lineup or bio removed on disk
// leaves the list; the open one says "<name> was deleted on disk".
import { api } from "../../lib/api";
import { editingIn, onFilesChanged, type FilesChange } from "../../lib/filesLive";
import { forgetResolved } from "../shared/resolve";
import { clone, roles, type RolesState } from "./store";
import { layoutPending, loadModelsStatus, readLayout, validateSoon } from "./sync";
import type { BioPayload, BioRow, LineupPayload, LineupRow, Pos, StateInfo } from "./types";

let started = false;
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
const touched = (c: FilesChange, name: string) => c.names.includes(name) || c.removed.includes(name);
const path = (kind: string, name: string) => `${kind}/${encodeURIComponent(name)}`;

/** The open lineup has edits not saved (the mapping, or a field of the Inspector being typed in). */
export const lineupDirty = (s: RolesState = roles.get()) => s.dirty || editingIn("roles-inspector-body");

/** The bio form holds edits not saved (the draft differs from the file it was read from, or a field is being typed in). */
export const bioDirty = (s: RolesState = roles.get()) =>
  !!s.bioDraft && !!s.bioData && (!same(s.bioDraft, s.bioData.raw) || editingIn("bio-form"));

/** Put a lineup read from disk in the editor; the selected card, and positions not yet saved, stay. */
export function showLineup(p: LineupPayload): void {
  const { positions, collapsed } = readLayout(p.layout);
  roles.update((st) => ({
    name: p.name, current: p, raw: clone(p.raw), graph: p.graph, findings: p.findings || [], saveProblems: [], dirty: false,
    past: [], future: [], sel: p.graph?.nodes.some((n) => n.id === st.sel) ? st.sel : "",
    positions: st.posFor === p.name ? { ...positions, ...st.positions } : positions,
    collapsed: st.posFor === p.name ? st.collapsed : collapsed, posFor: p.name, diskLineup: null, error: "",
  }));
}

/** Reload: the open lineup as the file has it now (the draft is dropped). */
export async function reloadLineup(): Promise<void> {
  const name = roles.get().diskLineup?.name || roles.get().name;
  const p = await api.get<LineupPayload>(path("lineup", name)).catch(() => null);
  if (p) showLineup(p);
  else roles.update(() => ({ diskLineup: { name, gone: true } }));
}

/** Close the lineup that went on disk (its draft too). */
export function closeLineup(): void {
  roles.update(() => ({ name: "", current: null, raw: null, graph: null, findings: [], dirty: false, past: [], future: [], sel: "", diskLineup: null }));
}

async function onLineups(c: FilesChange): Promise<void> {
  const rows = await api.get<LineupRow[]>("lineups").catch(() => null);
  if (Array.isArray(rows)) roles.update(() => ({ lineups: rows }));
  forgetResolved();
  const s = roles.get();
  if (!s.name || !s.current) return;
  if (Array.isArray(rows) && !rows.some((l) => l.name === s.name)) {
    if (!lineupDirty(s)) closeLineup();
    roles.update(() => ({ diskLineup: { name: s.name, gone: true } }));
    return;
  }
  if (!touched(c, s.name)) return;
  const p = await api.get<LineupPayload>(path("lineup", s.name)).catch(() => null);
  const now = roles.get();
  if (!p || now.name !== p.name || same(p.raw, now.current?.raw)) return; // our own save, or nothing new for this page
  if (lineupDirty(now)) roles.update(() => ({ diskLineup: { name: p.name, gone: false } }));
  else showLineup(p);
}

/** Reload: the open bio as the file has it now. */
export async function reloadBio(): Promise<void> {
  const name = roles.get().diskBio?.name || roles.get().bio;
  const b = await api.get<BioPayload>(path("bio", name)).catch(() => null);
  if (b && roles.get().bio === name) roles.update(() => ({ bioData: b, bioDraft: clone(b.raw), bioProblems: [], diskBio: null }));
  else if (!b) roles.update(() => ({ diskBio: { name, gone: true } }));
}

export function closeBio(): void {
  roles.update(() => ({ bio: "", bioData: null, bioDraft: null, bioProblems: [], diskBio: null }));
}

async function onBios(c: FilesChange): Promise<void> {
  const rows = await api.get<BioRow[]>("bios").catch(() => null);
  if (Array.isArray(rows)) roles.update(() => ({ bios: rows }));
  forgetResolved(); // a card's "runs on" may name a bio's model
  if (roles.get().raw) validateSoon(true); // the cards on a changed bio show its model
  const s = roles.get();
  if (!s.bio || !s.bioData) return;
  if (Array.isArray(rows) && !rows.some((b) => b.name === s.bio)) {
    if (!bioDirty(s)) closeBio();
    roles.update(() => ({ diskBio: { name: s.bio || s.bioData!.name, gone: true } }));
    return;
  }
  if (!touched(c, s.bio)) return;
  const b = await api.get<BioPayload>(path("bio", s.bio)).catch(() => null);
  const now = roles.get();
  if (!b || now.bio !== s.bio || same(b.raw, now.bioData?.raw)) return;
  if (bioDirty(now)) roles.update(() => ({ diskBio: { name: s.bio, gone: false } }));
  else roles.update(() => ({ bioData: b, bioDraft: clone(b.raw), bioProblems: [], diskBio: null }));
}

const near = (a: Pos | undefined, b: Pos) => !!a && Math.abs(a.x - b.x) < 1 && Math.abs(a.y - b.y) < 1;

async function onLayouts(c: FilesChange): Promise<void> {
  const name = roles.get().name;
  if (!name || !c.names.includes(name) || layoutPending()) return;
  const raw = await api.get<unknown>(path("layout", name)).catch(() => null);
  const now = roles.get();
  if (raw === null || now.name !== name || layoutPending()) return;
  const { positions, collapsed } = readLayout(raw);
  const was = Object.fromEntries(Object.entries(now.collapsed).filter(([, v]) => v));
  if (Object.entries(positions).every(([id, p]) => near(now.positions[id], p)) && same(was, collapsed)) return; // what this page saved
  roles.update((st) => ({ positions: { ...st.positions, ...positions }, collapsed }));
}

async function onConfig(): Promise<void> {
  const [info, rows] = await Promise.all([api.get<StateInfo>("state").catch(() => null), api.get<LineupRow[]>("lineups").catch(() => null)]);
  roles.update(() => ({ ...(info ? { info } : {}), ...(Array.isArray(rows) ? { lineups: rows } : {}) }));
  forgetResolved(); // "the default (<model>)" follows config.json's model
  void loadModelsStatus();
  if (roles.get().raw) validateSoon(true);
}

/** Start once (startRoles): the four handlers. */
export function startDisk(): void {
  if (started) return;
  started = true;
  onFilesChanged("lineups", (c) => void onLineups(c));
  onFilesChanged("bios", (c) => void onBios(c));
  onFilesChanged("layouts", (c) => void onLayouts(c));
  onFilesChanged("config", () => void onConfig());
}
