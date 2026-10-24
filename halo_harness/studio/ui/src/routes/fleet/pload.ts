// Feeds the Fleet panels' store (pstore.ts): the attention queue from
// `GET fleet/attention`, refetched when the watcher's `fleet` frame (action
// `attention`, session_id null) says the count changed and every POLL_MS
// while the tab shows; conflicts and rooms the same way; costs, health and
// the digest on demand. The activity log and the timeline lanes are built
// here from the feed: every agent's state change (read off the map's store,
// so a GET and a frame count alike), its tool calls (ticks), its text,
// the cards it opens, errors, the fleet's own frames and (3.2.0.0 R3) a pack's lines. Started once with
// the map's store (sync.ts startFleet).
import { api, ApiError } from "../../lib/api";
import { onEvent, type FeedFrame } from "../../lib/events";
import { allAgents, fleet, keyOf, localId } from "./store";
import { lineOf, packOf } from "../packs/events";
import { panels, type AttnRow, type Conflicts, type Costs, type Digest, type Health, type LogKind, type LogLine, type Seg } from "./pstore";

const POLL_MS = 6000;
const MAX_LOG = 600;
const MAX_SEGS = 120;
const KEEP_MS = 65 * 60 * 1000;
const ASKS = ["permission_request", "question", "plan_review", "approval_request"];
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
let seq = 0;
let pending = 0;

export async function loadAttention(): Promise<void> {
  try {
    const r = await api.get<{ rows: AttnRow[]; count: number }>("fleet/attention");
    const rows = Array.isArray(r.rows) ? r.rows : [];
    panels.update((s) => ({ attention: rows, attnCount: r.count ?? rows.length, attnLoaded: true, attnError: "", attnSel: rows.some((x) => x.id === s.attnSel) ? s.attnSel : rows[0]?.id || "" }));
  } catch (e) {
    panels.update(() => ({ attnLoaded: true, attnError: msg(e) }));
  }
}

export async function loadConflicts(): Promise<void> {
  try {
    const r = await api.get<Conflicts>("fleet/conflicts");
    panels.update(() => ({ conflicts: { conflicts: r.conflicts || [], rooms: r.rooms || [] } }));
  } catch {
    /* the map draws without them */
  }
}

export async function loadCosts(): Promise<void> {
  try {
    const r = await api.get<Costs>("fleet/costs");
    panels.update(() => ({ costs: r, costsError: "" }));
  } catch (e) {
    panels.update(() => ({ costsError: msg(e) }));
  }
}

export async function loadHealth(refresh = false): Promise<void> {
  panels.update(() => ({ healthBusy: true }));
  try {
    const r = await api.get<Health>("fleet/health", refresh ? { refresh: 1 } : undefined);
    panels.update(() => ({ health: r, healthError: "", healthAt: Date.now(), healthBusy: false }));
  } catch (e) {
    panels.update(() => ({ healthError: msg(e), healthBusy: false }));
  }
}

export async function loadDigest(sinceMs: number): Promise<Digest | null> {
  try {
    const r = await api.get<Digest>("fleet/digest", { since: Math.floor(sinceMs / 1000) });
    panels.update(() => ({ digest: r, digestOpen: true }));
    return r;
  } catch {
    return null;
  }
}

// -- the activity log ---------------------------------------------------------------------
function nameOf(key: string): string {
  const ref = allAgents(fleet.get()).find((r) => r.key === key);
  return ref ? ref.a.name || ref.a.role || ref.a.agent_id : key.split("|")[2] || "main";
}

function addLine(key: string, kind: LogKind, text: string, ts = Date.now()): void {
  if (!text) return;
  const [harness = "", session_id = "", agent_id = "main"] = key.split("|");
  panels.update((s) => {
    const last = s.log[s.log.length - 1];
    if (kind === "text" && last && last.kind === "text" && last.key === key && ts - last.ts < 8000) {
      const joined = (last.text + text).replace(/\s+/g, " ");
      return { log: [...s.log.slice(0, -1), { ...last, text: joined.length > 280 ? "..." + joined.slice(-277) : joined }] };
    }
    const line: LogLine = { n: ++seq, ts, key, harness, session_id, agent_id, kind, text: text.replace(/\s+/g, " ").slice(0, 280) };
    return { log: [...s.log, line].slice(-MAX_LOG) };
  });
}

function frameKey(f: FeedFrame): string {
  return keyOf(String(f.harness || localId() || ""), String(f.session_id || ""), String(f.agent_id || "main"));
}

function onFrame(f: FeedFrame): void {
  const d = (f.data || {}) as Record<string, unknown>;
  const ts = f.ts ? f.ts * 1000 : Date.now();
  if (f.event === "text_chunk" && f.session_id) addLine(frameKey(f), "text", String(d.text || ""), ts);
  else if (f.event === "tool_use_start" && f.session_id) {
    const key = frameKey(f);
    addLine(key, "tool", `${nameOf(key)} runs ${String(d.name || "a tool")}`, ts);
    tick(key, ts);
  } else if (f.event === "agent_event" && d.kind === "tool_call" && f.session_id) tick(frameKey(f), ts);
  else if (f.event === "tool_result" && d.is_error && f.session_id) addLine(frameKey(f), "error", `${String(d.name || "a tool")} failed: ${String(d.summary || d.content || "")}`, ts);
  else if (ASKS.includes(f.event) && f.session_id) addLine(frameKey(f), "ask", `${nameOf(frameKey(f))} asks: ${f.event.replace("_", " ")}${d.name ? " " + String(d.name) : ""}`, ts);
  else if (f.event === "error" && f.session_id) addLine(frameKey(f), "error", String(d.message || d.error || "error"), ts);
  else if (f.event === "pack_event" && packOf(f.data)) {
    const p = packOf(f.data)!;
    const l = lineOf(p.pack, p.kind, p.data);
    addLine(keyOf(String(f.harness || localId() || ""), "", "pack:" + p.pack), "pack", `${l.label} ${l.text}`, ts);
  }
  else if (f.event === "fleet") {
    const action = String(d.action || "");
    if (action === "attention") return;
    if (["join", "leave", "online", "offline"].includes(action)) {
      const h = fleet.get().harnesses.find((x) => x.id === f.harness);
      addLine(keyOf(String(f.harness || ""), "", ""), "fleet", `${h?.name || String(d.name || f.harness || "a harness")}: ${action}`, ts);
    }
  }
}

function tick(key: string, ts: number): void {
  panels.update((s) => ({ ticks: { ...s.ticks, [key]: [...(s.ticks[key] || []).filter((t) => ts - t < KEEP_MS), ts].slice(-400) } }));
}

/** A lane gains a segment when its agent's state changes (from GET fleet or a frame alike). */
function noteStates(): void {
  const now = Date.now();
  const s = panels.get();
  let lanes: Record<string, Seg[]> | null = null;
  for (const r of allAgents(fleet.get())) {
    const state = String(r.a.state || "");
    const segs = s.lanes[r.key];
    const last = segs?.[segs.length - 1];
    if (last && last.state === state) continue;
    lanes = lanes || { ...s.lanes };
    const t = !segs && r.a.since ? Math.min(now, Number(r.a.since) * 1000) : now;
    lanes[r.key] = [...(segs || []), { t, state }].slice(-MAX_SEGS);
    if (last || state !== "done") addLine(r.key, "state", `${r.a.name || r.a.role || r.a.agent_id} ${state}${r.a.current && state === "running" ? ": " + r.a.current : ""}`, now);
  }
  if (lanes) panels.update(() => ({ lanes: lanes! }));
}

/** Start once: the first reads, the feed handlers, the poll while the tab shows. */
export function startPanels(): void {
  if (panels.get().started) return;
  panels.update(() => ({ started: true }));
  onEvent("*", onFrame);
  onEvent("fleet", (f) => {
    const d = (f.data || {}) as { action?: string; count?: number };
    if (d.action !== "attention") return;
    panels.update(() => ({ attnCount: Number(d.count) || 0 }));
    window.clearTimeout(pending);
    pending = window.setTimeout(() => (void loadAttention(), void loadConflicts()), 150);
  });
  fleet.subscribe(noteStates);
  noteStates();
  window.setInterval(() => {
    if (document.hidden) return;
    void loadAttention();
    void loadConflicts();
  }, POLL_MS);
  void loadAttention();
  void loadConflicts();
}
