// Who the Live column follows and who its Steer box talks to (3.1.7.0 R1, the
// owner: "more of insight and ability to jump in and steer"). `pin` (the
// session store) is the one agent the column shows; with none, the Steer box
// at the column's foot talks to the chosen session's main agent (the root of
// its tree), so the steer is always at hand. A "steer" on a line's tag or a
// map node pins that agent and puts the keyboard in that box; outside Session
// it opens the Agent panel's box instead (Fleet keeps its own Steer).
// 3.3.0.0 R6 (the owner: "you can't really tell which call you are steering.
// Highlight what you are interacting with"): the steer has a TARGET -- the
// agent you chose (a row clicked, `s` on a row, Tab / Shift+Tab in the field,
// a node clicked), else the pin, else main -- and a target ROW (the row you
// chose it on, else that agent's newest row), outlined in the column and on
// the map; your steer lands as a row right under it (liveFeed.ts addSteer).
// While the field has the keyboard the column stops following (`composing`).
import { useMemo } from "react";
import { studio, useStore } from "../../lib/store";
import { layoutStore, patchPanel } from "../../lib/workspace/persist";
import { openAgentPanel, select } from "../fleet/actions";
import { focusSteer } from "../fleet/Steer";
import { fleet, findAgent, isLive, keyOf, localId, treeOf, useFleet, type FleetState, type Scope } from "../fleet/store";
import type { AgentKey, AgentRef } from "../fleet/types";
import { live, setSteerAnchor, type LiveLine } from "../shared/liveFeed";
import { chosenSession, sess, useSession } from "./store";

/** Show only `key` in the column ("" = every agent); the map selects it too, and the steer goes to it. */
export function pinTo(key: AgentKey): void {
  sess.update(() => ({ pin: key, follow: true, target: key, held: 0, hold: false }));
  if (key && findAgent(fleet.get(), key)) select(key);
}

/** A tag or a lane: pin its agent, or, when it is the pinned one, show everyone again. */
export function setPin(key: AgentKey): void {
  pinTo(sess.get().pin === key ? "" : key);
}

/** Make `key` the steer's target, held on its row `n` (0: its newest row); a pin on another agent moves to it. */
export function chooseTarget(key: AgentKey, n = 0): void {
  if (!key) return;
  sess.update((s) => ({ target: key, held: n, chosenAt: s.chosenAt + 1, hold: true, pin: s.pin && s.pin !== key ? key : s.pin }));
  if (findAgent(fleet.get(), key) && fleet.get().selected !== key) select(key);
}

/** A click on a map node: it is selected, and in Session it becomes the steer's target too. */
export function pickNode(key: AgentKey): void {
  if (studio.get().section === "session") chooseTarget(key);
  else select(key);
}

/** "steer" on a tag or a map node: in Session, pin it and focus the Live column's box; elsewhere the Agent panel's. */
export function steerAgent(key: AgentKey): void {
  if (!key) return;
  if (studio.get().section !== "session") {
    select(key);
    openAgentPanel();
    focusSteer("agent");
    return;
  }
  if (layoutStore("session").get().layout?.["session-live"]?.collapsed) patchPanel("session", "session-live", { collapsed: false }, false);
  pinTo(key);
  focusSteer("live");
}

/** The session the column's strip, its agent pick and its Steer box speak of: the chosen one, else the newest here. */
export function stripScope(s: FleetState): Scope {
  const ss = chosenSession(s);
  return { harness: localId(s) || "?", ...(ss ? { session: ss.session_id } : {}) };
}

export function useStripScope(): Scope {
  const harnesses = useFleet((s) => s.harnesses);
  const scope = useFleet((s) => s.scope);
  const { harness, session } = stripScope({ ...fleet.get(), harnesses, scope });
  return useMemo(() => ({ harness, ...(session ? { session } : {}) }), [harness, session]);
}

function stripAgents(s: FleetState, scope: Scope): AgentRef[] {
  const h = s.harnesses.find((x) => x.id === scope.harness);
  const ss = h?.sessions.find((x) => x.session_id === scope.session);
  return h && ss ? treeOf(ss.agents || []).map(({ a, depth }) => ({ key: keyOf(h.id, ss.session_id, a.agent_id), h, s: ss, a, depth })) : [];
}

/** That session's agents in tree order (the agent pick's rows). */
export function useStripAgents(): AgentRef[] {
  const harnesses = useFleet((s) => s.harnesses);
  const scope = useStripScope();
  return useMemo(() => stripAgents({ ...fleet.get(), harnesses }, scope), [harnesses, scope]);
}

export type SteerTo = { key: AgentKey; ref: AgentRef | null; main: boolean };

/** The chosen target, else the pinned agent, else the chosen session's main agent; `main` marks the root of its tree. */
export function steerTarget(s: FleetState, pin: AgentKey, target: AgentKey = ""): SteerTo {
  const want = target || pin;
  if (want) {
    const ref = findAgent(s, want);
    return { key: want, ref, main: !!ref && !ref.a.parent };
  }
  const ss = chosenSession(s);
  if (!ss) return { key: "", ref: null, main: true };
  const root = (ss.agents || []).find((a) => !a.parent) || (ss.agents || [])[0];
  const key = keyOf(localId(s), ss.session_id, root?.agent_id || "main");
  return { key, ref: findAgent(s, key), main: true };
}

export function useSteerTarget(): SteerTo {
  const pin = useSession((s) => s.pin);
  const target = useSession((s) => s.target);
  const harnesses = useFleet((s) => s.harnesses);
  const scope = useFleet((s) => s.scope);
  return useMemo(() => steerTarget({ ...fleet.get(), harnesses, scope }, pin, target), [pin, target, harnesses, scope]);
}

/** The steer target's key while Session shows ("" elsewhere): the map's node and the strip's lane light it. */
export function useTargetKey(): AgentKey {
  const on = useStore(studio, (s) => s.section === "session");
  const key = useSteerTarget().key;
  return on ? key : "";
}

/** The target row among `lines`: the held one when it is there, else the agent's newest row (0: none). */
export function targetRow(lines: LiveLine[], key: AgentKey, held: number): number {
  if (!key) return 0;
  if (held && lines.some((l) => l.n === held && l.key === key)) return held;
  for (let i = lines.length - 1; i >= 0; i--) if (lines[i].key === key) return lines[i].n;
  return 0;
}

/** Tab / Shift+Tab in the field: the next (previous) live agent of the session becomes the target ("": no other one). */
export function cycleTarget(dir: 1 | -1): AgentKey {
  const s = fleet.get();
  const st = sess.get();
  const rows = stripAgents(s, stripScope(s)).filter((r) => isLive(r.a));
  const cur = steerTarget(s, st.pin, st.target).key;
  const i = rows.findIndex((r) => r.key === cur);
  const next = rows.length ? rows[i < 0 ? (dir > 0 ? 0 : rows.length - 1) : (i + dir + rows.length) % rows.length] : undefined;
  if (!next || next.key === cur) return "";
  chooseTarget(next.key, 0);
  return next.key;
}

const newest = () => live.get().lines[live.get().lines.length - 1]?.n || 0;

/** The column stops following and remembers where (a scroll up, the field taking the keyboard). */
export function pauseFollow(): void {
  sess.update((s) => (s.follow ? { follow: false, pausedAt: newest() } : {}));
}

/** The Steer field took (or gave back) the keyboard: while it holds it the column does not move. */
export function setComposing(on: boolean): void {
  if (on) {
    pauseFollow();
    sess.update(() => ({ composing: true }));
  } else sess.update(() => ({ composing: false }));
}

/** The pill, Escape out of the field, Follow: follow the newest row again (the target stays, its row is no longer held in view). */
export function followAgain(): void {
  sess.update(() => ({ follow: true, hold: false }));
}

// a steer you send lands under its target row (the anchor), when it is the box's target
setSteerAnchor((key) => {
  const st = sess.get();
  const t = steerTarget(fleet.get(), st.pin, st.target);
  return t.key === key ? targetRow(live.get().lines, key, st.held) : 0;
});
