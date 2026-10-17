// Feeds the Roles store (3.0.7.0 R2): the lists once when Roles first shows
// (state, lineups, bios, tools, then the model catalog with best-for and the
// gym scores), the lineup open in the editor (`GET lineup/<name>`, its layout
// riding along), a `POST validate` 250 ms after every edit (the graph and the
// Problems panel follow the unsaved mapping), and the card positions and tier
// boxes saved with `PUT layout/<name>` 500 ms after the last move. The
// status bar's ROLES line follows the store.
import { api, ApiError } from "../../lib/api";
import { setSectionStatus } from "../../lib/store";
import { clone, roles, statusLine } from "./store";
import type { BioRow, Finding, Graph, GymScore, LineupPayload, LineupRow, ModelRow, ModelsStatus, Pos, StateInfo } from "./types";

const VALIDATE_MS = 250;
const SAVE_MS = 500;
let validateTimer = 0;
let saveTimer = 0;
let validateSeq = 0;

export const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));
const list = <T>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

/** The saved positions: `{nodes, tiers}` (3.0.7.0) or the flat `{id: {x, y}}` file before it. */
export function readLayout(raw: unknown): { positions: Record<string, Pos>; collapsed: Record<string, boolean> } {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const src = (r.nodes && typeof r.nodes === "object" ? r.nodes : r) as Record<string, unknown>;
  const positions: Record<string, Pos> = {};
  for (const [id, p] of Object.entries(src)) {
    const q = p as Partial<Pos> | null;
    if (id !== "nodes" && id !== "tiers" && q && typeof q.x === "number" && typeof q.y === "number" && isFinite(q.x) && isFinite(q.y)) positions[id] = { x: q.x, y: q.y };
  }
  const collapsed: Record<string, boolean> = {};
  for (const [name, v] of Object.entries((r.tiers && typeof r.tiers === "object" ? r.tiers : {}) as Record<string, { collapsed?: boolean }>)) if (v?.collapsed) collapsed[name] = true;
  return { positions, collapsed };
}

export async function loadLists(): Promise<void> {
  try {
    const [info, lineups, bios, tools] = await Promise.all([
      api.get<StateInfo>("state"),
      api.get<LineupRow[]>("lineups"),
      api.get<BioRow[]>("bios"),
      api.get<string[]>("tools").catch(() => []),
    ]);
    roles.update(() => ({ info, lineups: list(lineups), bios: list(bios), tools: list<string>(tools), loaded: true, error: "" }));
  } catch (e) {
    roles.update(() => ({ loaded: true, error: msg(e) }));
  }
}

export async function loadModels(): Promise<void> {
  const [models, bestFor, gym] = await Promise.all([
    api.get<ModelRow[]>("models").catch(() => []),
    api.get<Record<string, string[]>>("models/best-for").catch(() => ({})),
    api.get<{ scores: Record<string, GymScore> }>("gym").catch(() => ({ scores: {} })),
  ]);
  roles.update(() => ({ models: list(models), bestFor: bestFor || {}, gym: gym?.scores || {}, modelsLoaded: true }));
}

export async function loadModelsStatus(): Promise<void> {
  try {
    const st = await api.get<ModelsStatus>("models/status");
    roles.update(() => ({ modelsStatus: st }));
  } catch {
    /* the Models panel says it could not ask */
  }
}

/** Open `name` in the editor (unsaved edits ask first: the discard dialog). */
export async function openLineup(name: string, force = false): Promise<void> {
  const s = roles.get();
  if (!force && s.dirty && s.name && s.name !== name) {
    roles.update(() => ({ dialog: { kind: "discard", then: name } }));
    return;
  }
  try {
    const p = await api.get<LineupPayload>("lineup/" + encodeURIComponent(name));
    const { positions, collapsed } = readLayout(p.layout);
    roles.update((st) => ({
      name: p.name, current: p, raw: clone(p.raw), graph: p.graph, findings: p.findings || [], saveProblems: [], dirty: false,
      past: [], future: [], sel: st.name === p.name ? st.sel : "", positions, collapsed, posFor: p.name, error: "",
    }));
  } catch (e) {
    roles.update(() => ({ error: msg(e) }));
  }
}

/** Validate the edited mapping soon: the canvas, the cards' badges and the Problems panel follow it. */
export function validateSoon(now = false): void {
  window.clearTimeout(validateTimer);
  const run = async () => {
    const s = roles.get();
    if (!s.raw) return;
    const seq = ++validateSeq;
    try {
      const r = await api.post<{ problems: string[]; graph: Graph; findings: Finding[] }>("validate", { kind: "lineup", raw: s.raw, name: s.name });
      if (seq === validateSeq) roles.update(() => ({ graph: r.graph, findings: r.findings || [] }));
    } catch (e) {
      if (seq === validateSeq) roles.update(() => ({ findings: [{ id: "validate-error", severity: "blocks", text: msg(e), fix: "", node: "" }] }));
    }
  };
  if (now) void run();
  else validateTimer = window.setTimeout(() => void run(), VALIDATE_MS);
}

/** Cards moved (or the canvas laid out): the store now, the server 500 ms after the last move. */
export function movePositions(patch: Record<string, Pos>): void {
  roles.update((s) => ({ positions: { ...s.positions, ...patch } }));
  saveLayoutSoon();
}

export function setCollapsed(tier: string, on: boolean): void {
  roles.update((s) => ({ collapsed: { ...s.collapsed, [tier]: on } }));
  saveLayoutSoon();
}

function saveLayoutSoon(): void {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => void saveLayout(), SAVE_MS);
}

export async function saveLayout(): Promise<void> {
  const s = roles.get();
  if (!s.name || !s.graph) return;
  const nodes: Record<string, Pos> = {};
  for (const n of s.graph.nodes) if (s.positions[n.id]) nodes[n.id] = { x: Math.round(s.positions[n.id].x), y: Math.round(s.positions[n.id].y) };
  const tiers: Record<string, { collapsed: boolean }> = {};
  for (const t of s.graph.tiers) tiers[t.name] = { collapsed: !!s.collapsed[t.name] };
  try {
    await api.put("layout/" + encodeURIComponent(s.name), { positions: nodes, nodes, tiers });
  } catch {
    /* kept in the store; the next move saves again */
  }
}

/** Start once: the lists, the catalog, the active lineup; the status bar follows the store from now on. */
export function startRoles(): void {
  if (roles.get().started) return;
  roles.update(() => ({ started: true }));
  void (async () => {
    await loadLists();
    const s = roles.get();
    const first = s.info?.active_team && s.lineups.some((l) => l.name === s.info!.active_team) ? s.info.active_team : "";
    if (first && !s.name) await openLineup(first);
  })();
  void loadModels();
  let last = "";
  roles.subscribe(() => {
    const line = statusLine(roles.get());
    if (line !== last) {
      last = line;
      setSectionStatus("roles", line);
    }
  });
}
