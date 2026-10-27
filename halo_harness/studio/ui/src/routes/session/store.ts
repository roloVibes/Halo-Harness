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
// 3.2.2.0 R6: config.json moving on disk (`halo teams apply`, `halo config set
// model`: `files_changed`) reads GET fleet again: the sessions' lineup and model.
import { createStore, goSection, studio, useStore } from "../../lib/store";
import { select } from "../fleet/actions";
import { findAgent, fleet, isLive, keyOf, localId, parseKey, useFleet, type FleetState, type Scope } from "../fleet/store";
import { load as loadFleet, startFleet } from "../fleet/sync";
import { onFilesChanged } from "../../lib/filesLive";
import type { AgentKey, AgentRow, SessionRow } from "../fleet/types";

export type SessionUiView = "auto" | "start" | "workspace";
type Want = { session: string; key: AgentKey };
/** 3.1.5.0 R3: `pin` is the one agent the Live column shows (its tag clicked; "" = every agent), `follow` keeps its newest line in view.
 *  3.1.7.0 R1: `kind` the kinds it shows ("" = every kind, else tool | text | state | ask: LiveHead.tsx).
 *  3.3.0.0 R6 (steer.ts): `target` the agent the Steer box talks to when you chose one ("" = the pin, else main),
 *  `held` the row you chose it on (0 = its newest row), `chosenAt` counts the choices (the row scrolls into view once),
 *  `hold` following never pushes that row out of view (until you follow again: the pill, Escape, Follow),
 *  `composing` the Steer field has the keyboard, `pausedAt` the newest line when the column stopped following. */
type SessionState = {
  view: SessionUiView; chosen: string; want: Want | null; pin: AgentKey; follow: boolean; kind: string;
  target: AgentKey; held: number; chosenAt: number; hold: boolean; composing: boolean; pausedAt: number;
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

/** The session the Cost panel and the log speak of: the chosen one, else the newest live one here. */
export function chosenSession(s: FleetState): SessionRow | null {
  const all = localSessions(s);
  const sid = s.scope.session;
  if (sid) return all.find((x) => x.session_id === sid) || null;
  return [...all].sort((x, y) => (Number(y.started) || 0) - (Number(x.started) || 0))[0] || null;
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

/** Every studio or fleet change: the scope in and out of the section, the pick on enter, the session following the selection. */
function onChange(): void {
  if (busy) return;
  busy = true;
  try {
    const section = studio.get().section;
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
    if (s.loaded && want) {
      sess.update(() => ({ want: null }));
      needPick = false;
      session = want.session || parseKey(want.key).s;
      const key = want.key && findAgent(s, want.key) ? want.key : pickAgent(s, session);
      if (key && findAgent(s, key)) select(key);
    } else if (s.loaded && needPick) {
      needPick = false;
      const p = parseKey(s.selected);
      if (!s.selected || p.h !== harness || !findAgent(s, s.selected)) {
        const known = localSessions(s).some((x) => x.session_id === session);
        const key = pickAgent(s, known ? session : "");
        if (key && findAgent(s, key)) select(key);
      }
    }
    const sel = fleet.get().selected;
    if (sel !== lastSel) {
      lastSel = sel;
      const p = parseKey(sel);
      if (sel && p.h === harness) session = p.s;
    }
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
  onChange();
}

/** The section's `enter` (the "+" menu and the palette bring a panel up): the workspace, not the Start view. */
export function enterSession(): void {
  startSession();
  if (showsSessionStart(fleet.get(), sess.get().view)) setSessionView("workspace");
}

/** Open Session on a session or an agent (the links into it); with neither, on the newest working agent. */
export function openSession(t: { key?: AgentKey; session?: string } = {}): void {
  const session = t.session || (t.key ? parseKey(t.key).s : "");
  sess.update(() => ({ want: session || t.key ? { session, key: t.key || "" } : null }));
  startSession();
  if (studio.get().section === "session") onChange();
  else goSection("session");
}
