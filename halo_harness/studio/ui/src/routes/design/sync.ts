// Feeds the Design store (3.0.7.0 R3): the projects, the open project (its
// detail, its assets, the card positions from `GET layout/design:<slug>`),
// and the running turn. A turn's steps arrive as `design_turn` frames on the
// live feed (`/api/events`); while the feed is not open the page polls
// `turn/<id>?since=N` every 500 ms instead, the classic page's way, and a
// slow 3 s check covers a frame the feed dropped. Both paths fill the same
// event slots by index, so nothing shows twice. When the turn ends the
// project is read again and its history holds the turn.
import { api, ApiError, call as apiCall } from "../../lib/api";
import { changed, same } from "../../lib/diff";
import { feedState, onEvent, type FeedFrame } from "../../lib/events";
import { studio, toast, writeLocal } from "../../lib/store";
import { design, statusLine, versionsLine } from "./store";
import type { Asset, Detail, LiveTurn, Pos, ProjectRow, TurnEvent, TurnResult } from "./types";

const LAST = "halo.studio.design.project";
const SAVE_MS = 500;
let pollTimer = 0;
let saveTimer = 0;

const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));
export const call = <T>(method: string, path: string, body?: unknown) => {
  const slug = design.get().slug;
  return apiCall<T>(method, "design/" + encodeURIComponent(slug) + (path ? "/" + path : ""), body);
};

function readLocal(key: string): string {
  try {
    return localStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

function line(): void {
  const text = statusLine(design.get());
  studio.update((s) => (s.status.design === text ? {} : { status: { ...s.status, design: text } }));
}

export async function loadProjects(): Promise<ProjectRow[]> {
  try {
    const r = await api.get<{ projects: ProjectRow[] }>("design/projects");
    const rows = Array.isArray(r.projects) ? r.projects : [];
    design.update((s) => changed(s, { projects: rows, error: "" }));
    return rows;
  } catch (e) {
    design.update((s) => ({ projects: s.projects ?? [], error: msg(e) }));
    return design.get().projects || [];
  } finally {
    line();
  }
}

function readPositions(raw: unknown): Record<string, Pos> {
  const src = (raw && typeof raw === "object" && "nodes" in raw ? (raw as { nodes: unknown }).nodes : raw) as Record<string, Partial<Pos>> | null;
  const out: Record<string, Pos> = {};
  for (const [id, p] of Object.entries(src || {})) if (p && typeof p.x === "number" && typeof p.y === "number") out[id] = { x: p.x, y: p.y };
  return out;
}

/** Read the open project again (after a turn, an action); the store keeps what did not change. */
export async function reload(): Promise<void> {
  const slug = design.get().slug;
  if (!slug) return;
  try {
    const d = await call<Detail>("GET", "");
    if (design.get().slug !== slug) return;
    design.update((s) => {
      const sel = d.artboards.some((a) => a.id === s.sel) ? s.sel : d.artboards[0]?.id || "";
      return changed(s, { data: same(s.data, d), sel, error: "" });
    });
    if (d.live_turn && !design.get().turn) attach(d.live_turn, "(a turn that was already running)");
  } catch (e) {
    design.update(() => ({ error: msg(e) }));
  } finally {
    line();
  }
}

export async function loadAssets(): Promise<void> {
  try {
    const r = await call<{ assets: Asset[] }>("GET", "assets");
    design.update((s) => changed(s, { assets: r.assets || [] }));
  } catch {
    design.update((s) => changed(s, { assets: [] }));
  }
}

export async function openProject(slug: string): Promise<void> {
  writeLocal(LAST, slug);
  window.clearTimeout(pollTimer);
  design.update(() => ({ slug, data: null, loading: true, turn: null, view: {}, bust: {}, sel: "", assets: [], positions: {}, posFor: "", pinAt: null, pinOpen: "", editing: null, knobNote: {} }));
  await reload();
  design.update(() => ({ loading: false }));
  try {
    const raw = await api.get("layout/" + encodeURIComponent("design:" + slug));
    if (design.get().slug === slug) design.update(() => ({ positions: readPositions(raw), posFor: slug }));
  } catch {
    design.update(() => ({ posFor: slug }));
  }
  void loadAssets();
}

/** A card moved: the store now, the server 500 ms after the last move. */
export function movePositions(patch: Record<string, Pos>): void {
  design.update((s) => ({ positions: { ...s.positions, ...patch } }));
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    const s = design.get();
    if (!s.slug || !s.data) return;
    const nodes: Record<string, Pos> = {};
    for (const a of s.data.artboards) if (s.positions[a.id]) nodes[a.id] = { x: Math.round(s.positions[a.id].x), y: Math.round(s.positions[a.id].y) };
    void api.put("layout/" + encodeURIComponent("design:" + s.slug), { positions: nodes, nodes }).catch(() => null);
  }, SAVE_MS);
}

// -- the running turn ------------------------------------------------------------------
function put(tid: string, n: number, ev: TurnEvent): void {
  design.update((s) => {
    if (!s.turn || s.turn.id !== tid || s.turn.events[n]) return {};
    const events = s.turn.events.slice();
    events[n] = ev;
    return { turn: { ...s.turn, events } };
  });
}

async function finish(tid: string, result: TurnResult | null): Promise<void> {
  const t = design.get().turn;
  if (!t || t.id !== tid || t.done) return;
  window.clearTimeout(pollTimer);
  design.update((s) => ({ turn: s.turn && { ...s.turn, done: true, result }, bust: bump(s.bust, result) }));
  const r = result || ({ code: 1 } as TurnResult);
  if (r.cancelled) toast("Turn cancelled: what it wrote so far is saved as versions", "info", 4500);
  else if (r.code === 0) toast(`Turn done: ${versionsLine(r.versions) || "no artboard changed"}`, "done", 4500);
  else toast(`The turn ended with exit ${r.code}${r.error ? ": " + r.error : ""}`, "error", 6000);
  await reload();
  design.update((s) => (s.turn?.id === tid ? { turn: null } : {}));
}

function bump(bust: Record<string, number>, r: TurnResult | null): Record<string, number> {
  const out = { ...bust };
  for (const [aid] of r?.versions || []) out[aid] = (out[aid] || 0) + 1;
  return out;
}

async function pollTurn(tid: string): Promise<void> {
  const t = design.get().turn;
  if (!t || t.id !== tid || t.done) return;
  const since = t.events.findIndex((e) => !e) >= 0 ? t.events.findIndex((e) => !e) : t.events.length;
  try {
    const p = await call<{ events: TurnEvent[]; next: number; done: boolean; result: TurnResult | null }>("GET", `turn/${tid}?since=${since}`);
    p.events.forEach((ev, i) => put(tid, since + i, ev));
    if (p.done) return void finish(tid, p.result);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return void finish(tid, null);
  }
  pollTimer = window.setTimeout(() => void pollTurn(tid), feedState() === "open" ? 3000 : 500);
}

/** Follow turn `tid` of the open project (its frames, or the poll). */
export function attach(tid: string, prompt: string, label?: string): void {
  window.clearTimeout(pollTimer);
  const turn: LiveTurn = { id: tid, prompt, events: [], done: false, result: null, label };
  design.update(() => ({ turn }));
  line();
  pollTimer = window.setTimeout(() => void pollTurn(tid), feedState() === "open" ? 1500 : 300);
}

function onFrame(f: FeedFrame): void {
  const d = (f.data || {}) as { slug?: string; turn?: string; state?: string; n?: number; event?: TurnEvent; prompt?: string; result?: TurnResult };
  const s = design.get();
  if (!d.turn || d.slug !== s.slug) return;
  if (d.state === "started" && !s.turn) return attach(d.turn, d.prompt || "");
  if (!s.turn || s.turn.id !== d.turn) return;
  if (d.state === "event" && typeof d.n === "number" && d.event) put(d.turn, d.n, d.event);
  else if (d.state === "done") void finish(d.turn, d.result || null);
}

/** Start once: the feed handler, the projects, the last project opened (or the first). */
export function startDesign(): void {
  if (design.get().started) return;
  design.update(() => ({ started: true }));
  onEvent("design_turn", onFrame);
  void loadProjects().then((rows) => {
    const last = readLocal(LAST) || readLocal("halo-design-project");
    const pick = rows.find((p) => p.slug === last) || rows[0];
    if (pick) void openProject(pick.slug);
  });
}
