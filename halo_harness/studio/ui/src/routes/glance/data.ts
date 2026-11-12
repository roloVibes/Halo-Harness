// The glance's facts (3.4.1.0 R4, `/?mode=glance`; docs/STUDIO-live.md "The glance"). It reads what Studio's own page
// reads, through the same client and the same feed: GET fleet (the sessions and their agents), GET fleet/attention
// (what waits on you), GET fleet/caps (the caps), an agent's tail for the backlog, GET settings/values (the alert's
// channel), and /api/events. No route of its own. Its one write is an answer (fleet/extras.ts answerRow: POST
// fleet/attention/answer with the token and the owner proof, as Attention sends it). `heard` is the last time Studio
// answered (a read or a feed frame); past STALE_MS the page says it is stale. The feed reconnects by itself (lib/events),
// and when the page shows again it reads everything once more and reopens a feed that went down.
import { api } from "../../lib/api";
import { connectEvents, onEvent, onFeedState, type FeedState } from "../../lib/events";
import { createStore, studio, useStore } from "../../lib/store";
import { startFeed } from "../../shell/feed";
import { loadAttention } from "../fleet/pload";
import { panels } from "../fleet/pstore";
import { load, startFleet } from "../fleet/sync";
import type { Harness, SessionRow } from "../fleet/types";
import { startLiveTree } from "../shared/liveTree";

export const STALE_MS = 15_000;
const CAPS_MS = 30_000;
export type CapsView = { caps: Record<string, number | null>; reached: { scope: string; key: string; label: string }[] };
type GlanceState = { heard: number; feed: FeedState; caps: CapsView | null; lit: string; started: boolean };

export const glance = createStore<GlanceState>({ heard: 0, feed: "off", caps: null, lit: "", started: false });
export const useGlance = <S,>(pick: (s: GlanceState) => S): S => useStore(glance, pick);

const heard = () => glance.update((s) => (Date.now() - s.heard > 500 ? { heard: Date.now() } : {}));

async function loadCaps(): Promise<void> {
  try {
    const c = await api.get<CapsView>("fleet/caps");
    glance.update(() => ({ caps: { caps: c.caps || {}, reached: Array.isArray(c.reached) ? c.reached : [] } }));
    heard();
  } catch {
    /* the spend says "no cap read" until a read lands */
  }
}

/** Everything once more: the page showed again, or the feed came back. */
function again(): void {
  void load();
  void loadAttention();
  void loadCaps();
  if (glance.get().feed !== "open" && glance.get().feed !== "connecting") connectEvents("all");
}

/** Start once: the feed, the fleet's sessions and the queue (not its catalogs or missions), the live lines, the caps. */
export function startGlance(): void {
  if (glance.get().started) return;
  glance.update(() => ({ started: true }));
  studio.update(() => ({ section: "session" })); // the Session-gated readers (the live tree, its backlog) run; nothing is saved
  startFeed();
  startFleet(true);
  startLiveTree(true);
  onFeedState((s) => {
    glance.update(() => ({ feed: s }));
    if (s === "open") heard();
  });
  onEvent("*", heard);
  let rows = panels.get().attention;
  panels.subscribe(() => {
    const p = panels.get();
    if (p.attention !== rows && !p.attnError) heard();
    rows = p.attention;
  });
  window.setInterval(() => void loadCaps(), CAPS_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) again();
  });
  void loadCaps();
}

const money = (x: number) => `$${x >= 1 ? x.toFixed(2) : x.toFixed(3)}`;
const today = (t: number | null | undefined) => !!t && new Date(t * 1000).toDateString() === new Date().toDateString();
const projectOf = (s: SessionRow) =>
  String(s.project?.repo || s.project?.root || s.cwd || "").replace(/\\/g, "/").replace(/\/+$/, "").split("/").pop() || "no project";

export type Spend = { spent: string; cap: string; pct: number | null; reached: boolean };

function total(rows: SessionRow[]): { usd: number; priced: number; open: boolean } {
  let usd = 0;
  let priced = 0;
  let open = false;
  for (const s of rows) {
    if (typeof s.cost_usd === "number" && isFinite(s.cost_usd)) (usd += s.cost_usd), (priced += 1);
    else open = true;
    if (s.cost_complete === false) open = true;
  }
  return { usd, priced, open };
}

/** Today's spend (the sessions started today, as the caps count them) against the first cap set of this machine's, the
 *  watched session's project's, the fleet's; honest: a session with no price makes it "$x+" (or "unknown" when nothing
 *  was priced), never $0 for what Halo cannot price; no cap: "no cap set". */
export function spendOf(harnesses: Harness[], caps: CapsView | null, sid: string): Spend {
  const local = harnesses.find((h) => h.local);
  const mine = (local?.sessions || []).filter((s) => today(s.started));
  const all = harnesses.flatMap((h) => h.sessions || []).filter((s) => today(s.started));
  const watched = (local?.sessions || []).find((s) => s.session_id === sid);
  const project = watched ? projectOf(watched) : "";
  const c = caps?.caps || {};
  const scopes: [string, string, number | null | undefined, SessionRow[]][] = [
    ["harness", "this machine's cap", c.per_harness_usd_per_day, mine],
    ["project", `the cap on ${project}`, project ? c.per_project_usd_per_day : null, all.filter((s) => projectOf(s) === project)],
    ["fleet", "the fleet's cap", c.fleet_usd_per_day, all],
  ];
  const first = scopes.find((x) => !!x[2]);
  const t = total(first ? first[3] : mine);
  const rows = (first ? first[3] : mine).length;
  const spent = rows && !t.priced ? "unknown" : `${money(t.usd)}${t.open ? "+" : ""}`;
  if (!caps) return { spent, cap: "the caps are not read yet", pct: null, reached: false };
  if (!first) return { spent, cap: "no cap set", pct: null, reached: false };
  const cap = Number(first[2]);
  const reached = (caps.reached || []).some((r) => r.scope === first[0]);
  return { spent, cap: `of ${money(cap)} a day, ${first[1]}`, pct: spent === "unknown" ? null : Math.min(1, t.usd / cap), reached };
}

/** "12 min", "1 h 04 min", "under a minute" since `t0` (unix seconds). */
export function elapsedWords(t0: number | null | undefined, nowMs: number): string {
  if (!t0) return "";
  const m = Math.floor(Math.max(0, nowMs / 1000 - t0) / 60);
  return m < 1 ? "under a minute" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

/** "8 s ago", "3 min ago" for a moment in unix seconds. */
export function agoWords(ts: number, nowMs: number): string {
  const s = Math.max(0, Math.round(nowMs / 1000 - ts));
  return s < 60 ? `${s} s ago` : s < 3600 ? `${Math.floor(s / 60)} min ago` : `${Math.floor(s / 3600)} h ago`;
}
