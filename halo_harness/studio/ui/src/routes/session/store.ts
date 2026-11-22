// The Session section's own state (3.1.4.0 R2, "The session dashboard"):
// which view shows (the Start view until this harness has a live session),
// the session chosen while you are away, and the scope it puts on the Fleet
// stores while it shows (routes/fleet/scope.ts: this harness, and the chosen
// session; cleared when you leave, so Fleet keeps everything). The chosen
// session follows the agent you select on the map; a link (the Fleet rail, a
// map node's menu, the Roles Live tab, the Orchestra run line, `/studio`,
// `?mode=session&session=<id>`, a `focus` frame) opens Session on a session
// or an agent with `openSession`. Entering with nothing of this harness
// selected selects the newest working agent of the chosen (else any) session.
// 3.6.0.2 R1: the chosen session is ONE function (`chosenSession`, routes/session/pick.ts) that Cost, Prompt, the Feed
// and the Live drawer read; with no pick it is the newest open session (never a Studio one with no message yet while
// another is open), written into the scope at once; one that ends stays picked (T8). A pick this page never saw listed
// is given up after two reads without it (a stale link), unless this page started it. 3.6.0.11: only a pick he made
// by hand is kept; the page's own follows the newest open session on each fresh list read (pick.ts autoPick).
// 3.2.2.0 R6: config.json moving on disk (`halo teams apply`, `halo config set
// model`: `files_changed`) reads GET fleet again: the sessions' lineup and model.
import { createStore, goSection, studio, useStore } from "../../lib/store";
import { select } from "../fleet/actions";
import { findAgent, fleet, isLive, keyOf, localId, parseKey, useFleet, type FleetState, type Scope } from "../fleet/store";
import { load as loadFleet, startFleet } from "../fleet/sync";
import { onFilesChanged } from "../../lib/filesLive";
import type { AgentKey, AgentRow, SessionRow } from "../fleet/types";
import { onEvent } from "../../lib/events";
import { autoPick, followerOf, hisAgent, livePick, noteAutoMove, noteBuild, noteRows, staleList, steerText } from "./pick";
import { prompt } from "./promptStore";
import { keepOpen } from "../crew/map/built";
import { startFlowFiles } from "./flowFiles";
import { startLit } from "../crew/map/litStore";
import { livePickAway, setAgentsView } from "../agents/store";

export type SessionUiView = "auto" | "start" | "workspace";
type Want = { session: string; key: AgentKey };
/** 3.1.5.0 R3: `pin` is the one agent the Live column shows (its tag clicked; "" = every agent), `follow` keeps its newest line in view.
 *  3.1.7.0 R1: `kind` the kinds it shows ("" = every kind, else tool | text | state | ask: LiveHead.tsx).
 *  3.3.0.0 R6 (steer.ts): `target` the agent the Steer box talks to when you chose one ("" = the pin, else main),
 *  `held` the row you chose it on (0 = its newest row), `chosenAt` counts the choices (the row scrolls into view once),
 *  `hold` following never pushes that row out of view (until you follow again: the pill, Escape, Follow),
 *  `composing` the Steer field has the keyboard, `pausedAt` the newest line when the column stopped following.
 *  3.6.0.11: `steer` the Steer box is open (off on every load, never saved: steer.ts openSteer / closeSteer). */
type SessionState = {
  view: SessionUiView; chosen: string; want: Want | null; pin: AgentKey; follow: boolean; kind: string;
  target: AgentKey; held: number; chosenAt: number; hold: boolean; composing: boolean; pausedAt: number; steer: boolean;
  /** 3.3.16.2: the Thinking view (LiveHead.tsx): only THINK rows and the rows they led to; `pair` only one pair's talk (Conversations). */
  think: boolean; pair: string;
};

function urlWant(): Want | null {
  if (!/[?&]mode=session(&|$)/.test(location.search)) return null;
  const session = new URLSearchParams(location.search).get("session") || "";
  return session ? { session, key: "" } : null;
}

export const sess = createStore<SessionState>({
  view: (/[?&]view=(start|workspace)/.exec(location.search)?.[1] as SessionUiView) || "auto",
  chosen: "",
  want: urlWant(),
  pin: "",
  follow: true,
  kind: "",
  target: "",
  held: 0,
  chosenAt: 0,
  hold: false,
  composing: false,
  pausedAt: 0,
  steer: false,
  think: false,
  pair: "",
});

export function useSession<S>(select: (s: SessionState) => S): S {
  return useStore(sess, select);
}

/** This harness's sessions (the Fleet store's local harness). */
export function localSessions(s: FleetState): SessionRow[] {
  const id = localId(s);
  return s.harnesses.find((h) => h.id === id)?.sessions || [];
}

/** The Start view: asked for, or this harness has no live session. */
export function showsSessionStart(s: FleetState, view: SessionUiView): boolean {
  if (view !== "auto") return view === "start";
  return s.loaded && !localSessions(s).length;
}

export function useSessionStart(): boolean {
  const view = useSession((x) => x.view);
  return useFleet((s) => showsSessionStart(s, view));
}

export function setSessionView(view: SessionUiView): void {
  sess.update(() => ({ view }));
}

const newest = (rows: AgentRow[]) => [...rows].sort((a, b) => (Number(b.since) || 0) - (Number(a.since) || 0))[0];

/** The agent to show: the newest working one (of `sid`, else of every session here), else the newest live, else the newest session's main agent. */
export function pickAgent(s: FleetState, sid = ""): AgentKey {
  const h = localId(s);
  const all = localSessions(s);
  const pool = sid ? all.filter((x) => x.session_id === sid) : all;
  const rows = pool.flatMap((ss) => (ss.agents || []).map((a) => ({ ...a, sid: ss.session_id })));
  const a = newest(rows.filter((x) => x.state === "running")) || newest(rows.filter(isLive));
  if (a) return keyOf(h, (a as AgentRow & { sid: string }).sid, a.agent_id);
  const ss = [...pool].sort((x, y) => (Number(y.started) || 0) - (Number(x.started) || 0))[0];
  if (!ss) return "";
  const main = (ss.agents || []).find((x) => !x.parent) || (ss.agents || [])[0];
  return keyOf(h, ss.session_id, main?.agent_id || "main");
}

/** R1: the session Cost, Prompt, the Feed and the Live drawer speak of: the picked one while it is open (null once it
 *  ended: T8), else the newest open one here (pick.ts `livePick`). */
export function chosenSession(s: FleetState): SessionRow | null {
  return livePick(localSessions(s), s.scope.session || sess.get().chosen);
}

function setScope(next: Scope): void {
  const cur = fleet.get().scope;
  if ((cur.harness || "") === (next.harness || "") && (cur.session || "") === (next.session || "")) return;
  fleet.update(() => ({ scope: next.harness ? { harness: next.harness, ...(next.session ? { session: next.session } : {}) } : {} }));
}

let started = false;
let busy = false;
let lastSection = "";
let lastSel = "";
let needPick = false;
let byHand = false; // 3.6.0.11: the pick is his (Change session, a link, a focus frame, an agent, a pin or a steer target he chose)
let ownSel = ""; // the agent this store selected itself (not his selection)
let autoSeen = -1; // the list read autoPick last looked at
const own = (s: FleetState, key: AgentKey) => void (key && findAgent(s, key) && ((ownSel = key), select(key)));

/** Every studio or fleet change: the scope in and out of the section, the pick on enter, the session following the selection. */
function onChange(): void {
  if (busy) return;
  busy = true;
  try {
    const section = studio.get().section;
    const f = fleet.get();
    if (f.loaded && !f.error) noteRows(localSessions(f), Date.now() / 1000); // R4: a session gone from the rows ended
    if (f.loaded && !f.error) keepOpen(localSessions(f).map((r) => r.session_id)); // R29: its tags go with it
    if (section !== "session") {
      if (lastSection === "session") {
        sess.update(() => ({ chosen: fleet.get().scope.session || "" }));
        setScope({});
      }
      lastSection = section;
      return;
    }
    if (lastSection !== "session") needPick = true;
    lastSection = section;
    const s = fleet.get();
    const harness = localId(s);
    let session = s.scope.harness ? s.scope.session || "" : sess.get().chosen;
    const want = sess.get().want;
    // the session LIST read again (GET live, a sessions frame: listReads), never an agent frame of another session
    const gaveUp = s.loaded && !s.error && staleList(s.listReads, localSessions(s), want ? "" : session);
    if (gaveUp) (session = "", (needPick = true), (byHand = false)); // R1: a pick never listed in two reads: Session as with no pick
    // 3.6.0.2 P31: a pick that left the list moves to the row that follows it (/clear, a fork, /resume in its terminal)
    const heir = s.loaded && !s.error && !want ? followerOf(localSessions(s), session) : null;
    if (heir) {
      session = heir.session_id;
      const key = pickAgent(s, session); // its main agent, as a pick on entering selects one
      own(s, key);
    }
    if (s.loaded && want) {
      sess.update(() => ({ want: null }));
      (needPick = false), (byHand = true);
      session = want.session || parseKey(want.key).s;
      const key = want.key && findAgent(s, want.key) ? want.key : pickAgent(s, session);
      own(s, key);
    } else if (s.loaded && needPick) {
      needPick = false;
      // R1: the kept pick stays the pick (open, ended: T8, or not listed yet); with none, the newest open session, whose
      // newest working agent is selected (as before 3.6.0.2)
      if (!session) session = livePick(localSessions(s), "")?.session_id || "";
      const p = parseKey(s.selected);
      if (session && (gaveUp || !s.selected || p.h !== harness || !findAgent(s, s.selected))) {
        const key = pickAgent(s, session); // an agent OF the kept session only
        own(s, key);
      }
    }
    const sel = fleet.get().selected;
    if (sel !== lastSel) {
      lastSel = sel;
      const p = parseKey(sel);
      if (sel && p.h === harness) session = p.s;
    }
    if (s.loaded && !session) session = livePick(localSessions(s), "")?.session_id || ""; // R1: once drawn, written down
    if (s.loaded && !s.error && s.listReads !== autoSeen) { // 3.6.0.11: each fresh read of the list; text being typed holds it
      autoSeen = s.listReads;
      const ss = sess.get();
      if (hisAgent(harness, sel, ownSel, ss.pin, ss.target)) byHand = true; // an agent he chose, a pin, a steer target
      const typing = !!prompt.get().draft.trim() || (ss.steer && !!steerText().trim()); // the Prompt box, the open Steer box
      const to = autoPick(localSessions(s), session, byHand, typing);
      if (to !== session) (session = to, noteAutoMove(to), own(s, pickAgent(s, to)));
    }
    if (session && sess.get().chosen !== session) sess.update(() => ({ chosen: session }));
    setScope({ harness: harness || "?", session });
  } finally {
    busy = false;
  }
}

/** Start once: the Fleet stores and the two subscriptions. */
export function startSession(): void {
  if (started) return;
  started = true;
  startFleet();
  onFilesChanged("config", () => void loadFleet());
  studio.subscribe(onChange);
  fleet.subscribe(onChange);
  startLit(); // 3.6.0.2 R29: a build is heard with the drawer closed too (the view-bar word)
  startFlowFiles(() => (fleet.get().loaded && !fleet.get().error ? localSessions(fleet.get()) : [])); // 3.6.0.9 V: a plain write's line
  onEvent("builder_done", (f) => noteBuild(f.session_id || "", (f.data || {}) as Record<string, unknown>, Date.now() / 1000)); // R4
  onChange();
}

/** The section's `enter` (the "+" menu and the palette bring a panel up): the workspace, not the Start view. */
export function enterSession(): void {
  startSession();
  if (showsSessionStart(fleet.get(), sess.get().view)) setSessionView("workspace");
}

/** 3.6.0.2 R18 R34: [Open in Agents -> Live] (a step-in card's, the Live drawer's): Agents -> 4 · Live opens with
 *  `sess.chosen` = this session (the session Agents -> Live opens on). */
export function openInLive(sid: string): void {
  if (sid) sess.update(() => ({ chosen: sid }));
  if (sid) livePickAway.update(() => ({ sid: "", at: "" })); // R1: a pick here replaces another machine's picked in Live
  if (sid && studio.get().section === "session") setScope({ harness: localId(fleet.get()) || "?", session: sid }); // kept on leaving
  setAgentsView("live");
  goSection("agents", "live");
}

/** Open Session on a session or an agent (the links into it); with neither, on the newest working agent. */
export function openSession(t: { key?: AgentKey; session?: string } = {}): void {
  const session = t.session || (t.key ? parseKey(t.key).s : "");
  sess.update(() => ({ want: session || t.key ? { session, key: t.key || "" } : null }));
  startSession();
  if (studio.get().section === "session") onChange();
  else goSection("session");
}
