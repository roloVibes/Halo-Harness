// Feeds the Org store (store.ts) with ONE diffed poller (3.0.7.0 R3): every
// POLL_MS while Org is the section on screen and the tab is visible, it reads
// `pc/status` and, with a linked company, the company, its agents, issues,
// goals and projects through the proxy; each list keeps its unchanged rows
// (lib/diff reuse), and the store is patched only with what changed, so a
// quiet company re-renders nothing (the classic page redrew everything every
// 8 s). The canvas positions come from `GET layout/pc:<id>` once per company
// (the flat `{id: {x, y}}` file or the `{nodes, tiers}` shape) and go back
// with `PUT layout/pc:<id>` 500 ms after the last drag.
import { api, ApiError } from "../../lib/api";
import { changed, reuse, same } from "../../lib/diff";
import { studio } from "../../lib/store";
import { linkedId, org, statusLine } from "./store";
import type { Agent, Company, Goal, Issue, PcStatus, Pos, Project } from "./types";

export const POLL_MS = 3000;
const SAVE_MS = 500;
let saveTimer = 0;
let inflight = false;
let lastSection = 0;

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const list = <T>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const visible = () => !document.hidden && studio.get().section === "org";

function readPositions(raw: unknown): Record<string, Pos> {
  const src = raw && typeof raw === "object" && "nodes" in (raw as object) && typeof (raw as { nodes: unknown }).nodes === "object"
    ? (raw as { nodes: Record<string, unknown> }).nodes
    : (raw as Record<string, unknown>) || {};
  const out: Record<string, Pos> = {};
  for (const [id, p] of Object.entries(src || {})) {
    const q = p as Partial<Pos> | null;
    if (q && typeof q.x === "number" && typeof q.y === "number" && isFinite(q.x) && isFinite(q.y)) out[id] = { x: q.x, y: q.y };
  }
  return out;
}

async function loadPositions(cid: string): Promise<void> {
  try {
    const raw = await api.get("layout/" + encodeURIComponent("pc:" + cid));
    if (org.get().posFor !== cid) org.update(() => ({ positions: readPositions(raw), posFor: cid }));
  } catch {
    org.update(() => ({ positions: {}, posFor: cid }));
  }
}

/** One poll: status, then (with a linked company) the company's rows; only the changes reach the store. */
export async function poll(): Promise<void> {
  if (inflight) return;
  inflight = true;
  try {
    let status: PcStatus;
    try {
      status = await api.get<PcStatus>("pc/status");
    } catch (e) {
      org.update((s) => ({ loaded: true, ...changed(s, { error: msg(e) }) }));
      return;
    }
    const s0 = org.get();
    const next = { ...s0, status: same(s0.status, status) };
    const cid = linkedId(next);
    if (!cid) {
      org.update((s) => ({ loaded: true, ...changed(s, { status: next.status, company: null, agents: [], issues: [], goals: [], projects: [], error: "" }) }));
      return;
    }
    const pc = (path: string) => api.get<unknown>("pc/" + path);
    const [company, agents, issues, goals, projects] = await Promise.all([
      pc(`companies/${cid}`).catch(() => null),
      pc(`companies/${cid}/agents`).catch(() => null),
      pc(`companies/${cid}/issues`).catch(() => []),
      pc(`companies/${cid}/goals`).catch(() => []),
      pc(`companies/${cid}/projects`).catch(() => []),
    ]);
    if (org.get().posFor !== cid) await loadPositions(cid);
    org.update((s) => ({
      loaded: true,
      ...changed(s, {
        status: next.status,
        company: same(s.company, (company as Company) || s.company),
        agents: agents === null ? s.agents : reuse(s.agents, list<Agent>(agents)),
        issues: reuse(s.issues, list<Issue>(issues)),
        goals: reuse(s.goals, list<Goal>(goals)),
        projects: reuse(s.projects, list<Project>(projects)),
        error: agents === null ? "Studio could not read the company's agents" : "",
      }),
    }));
  } finally {
    inflight = false;
    const line = statusLine(org.get());
    studio.update((s) => (s.legacy.org === line ? {} : { legacy: { ...s.legacy, org: line } }));
  }
}

/** Start once: the first read now, then the poll while Org shows. */
export function startOrg(): void {
  if (org.get().started) return;
  org.update(() => ({ started: true }));
  void poll();
  void loadLineups();
  window.setInterval(() => {
    if (visible()) void poll();
  }, POLL_MS);
  let was = studio.get().section;
  studio.subscribe(() => {
    const now = studio.get().section;
    if (now === was) return;
    was = now;
    if (now === "org" && org.get().started && Date.now() - lastSection > 1000) {
      lastSection = Date.now(); // coming back to Org: read now, not on the next tick
      void poll();
    }
  });
}

export async function loadLineups(): Promise<void> {
  try {
    const rows = await api.get<{ name: string }[]>("lineups");
    org.update((s) => changed(s, { lineups: list<{ name: string }>(rows).map((r) => r.name).filter(Boolean) }));
  } catch {
    /* the Sync and Pull dialogs say there is no lineup */
  }
}

/** A card moved (or the canvas was laid out): the store now, the server 500 ms after the last move. */
export function movePositions(patch: Record<string, Pos>): void {
  org.update((s) => ({ positions: { ...s.positions, ...patch } }));
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => void savePositions(), SAVE_MS);
}

export async function savePositions(): Promise<void> {
  const s = org.get();
  const cid = linkedId(s);
  if (!cid) return;
  const nodes: Record<string, Pos> = {};
  for (const a of s.agents) if (s.positions[a.id]) nodes[a.id] = { x: Math.round(s.positions[a.id].x), y: Math.round(s.positions[a.id].y) };
  try {
    // `positions` is the flat layout file; `nodes` is the same map for the {nodes, tiers} shape
    await api.put("layout/" + encodeURIComponent("pc:" + cid), { positions: nodes, nodes });
  } catch {
    /* kept in the store; the next move saves again */
  }
}
