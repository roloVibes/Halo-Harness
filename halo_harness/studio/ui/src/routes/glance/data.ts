// The glance's facts (3.4.1.0 R4, `/?mode=glance`; docs/STUDIO-live.md "The glance"). It reads what Studio's own page
// reads, through the same client and the same feed: GET fleet (the sessions and their agents), GET fleet/attention
// (what waits on you), GET fleet/caps (the caps), an agent's tail for the backlog, GET settings/values (the alert's
// channel), and /api/events. No route of its own. Its one write is an answer (fleet/extras.ts answerRow: POST
// fleet/attention/answer with the token and the owner proof, as Attention sends it). `heard` is the last time Studio
// answered (a read or a feed frame); past STALE_MS the page says it is stale. The feed reconnects by itself (lib/events),
// and when the page shows again it reads everything once more and reopens a feed that went down.
// 3.4.1.1 (63): a Studio restarted on the same port has a NEW key (the token is per launch, never kept or reused), so
// the open page's reads turn from "no answer" to 401: the page says so, revokes its key (every request and the feed stop
// asking) and points at Studio's "Open the glance". The same Studio back (a blip, the SSH forward re-made) answers 200
// and the page is live again by itself. While the page has not heard Studio for PROBE_MS it asks every PROBE_MS.
import { api, ApiError, onTokenChange, revoke } from "../../lib/api";
import { connectEvents, disconnectEvents, onEvent, onFeedState, type FeedState } from "../../lib/events";
import { createStore, studio, useStore } from "../../lib/store";
import { startFeed } from "../../shell/feed";
import { loadAttention } from "../fleet/pload";
import { panels } from "../fleet/pstore";
import { load, startFleet } from "../fleet/sync";
import type { CostsView } from "../agents/live/spend";
import { startLiveTree } from "../shared/liveTree";

export const STALE_MS = 15_000;
const CAPS_MS = 30_000;
const PROBE_MS = 3_000;
/** 3.4.1.1 (65): GET fleet/costs -- the spend every other figure reads (live/caps.spend over each harness's today from
 *  its records, finished sessions too) and the caps -- never the drawn session's own spend. */
export type CapsView = CostsView;
/** `rekeyed`: Studio no longer takes this page's key ("restarted": it had answered before; "refused": never). */
type GlanceState = { heard: number; feed: FeedState; caps: CapsView | null; lit: string; started: boolean; rekeyed: "" | "restarted" | "refused" };

export const glance = createStore<GlanceState>({ heard: 0, feed: "off", caps: null, lit: "", started: false, rekeyed: "" });
export const useGlance = <S,>(pick: (s: GlanceState) => S): S => useStore(glance, pick);

const heard = () => glance.update((s) => (Date.now() - s.heard > 500 ? { heard: Date.now() } : {}));
let capsAt = 0;

/** One read: the costs (`full`) or a light probe (the caps); a 401 is a key Studio does not take, never retried. */
async function ask(full: boolean): Promise<void> {
  if (glance.get().rekeyed) return;
  if (full) capsAt = Date.now();
  try {
    const c = await api.get<CapsView>(full ? "fleet/costs" : "fleet/caps");
    if (full) glance.update(() => ({ caps: { ...c, caps: c.caps || {}, reached: Array.isArray(c.reached) ? c.reached : [] } }));
    heard();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) rekeyed();
    /* else: no answer; the spend says "not read yet" until a read lands */
  }
}
const loadCaps = () => ask(true);

function rekeyed(): void {
  glance.update((s) => ({ rekeyed: s.heard ? "restarted" : "refused" }));
  revoke();
  disconnectEvents();
}

/** Every PROBE_MS: the costs when due, else a light probe while Studio has not been heard (a restart is told at once). */
function probe(): void {
  const s = glance.get();
  if (s.rekeyed || document.hidden) return;
  if (Date.now() - capsAt >= CAPS_MS) void ask(true);
  else if (Date.now() - s.heard >= PROBE_MS) void ask(false);
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
  window.setInterval(probe, PROBE_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !glance.get().rekeyed) again();
  });
  onTokenChange(() => { glance.update(() => ({ rekeyed: "" })); again(); }); // a fresh address pasted over the tab
  void loadCaps();
}

// 3.4.1.1 (65): the spend against its cap is the pure module's (agents/live/spend.ts), from GET fleet/costs.
export { spendOf, type Spend } from "../agents/live/spend";

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
