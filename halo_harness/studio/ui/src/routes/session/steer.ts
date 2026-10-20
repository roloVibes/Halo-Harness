// Who the Live column follows and who its Steer box talks to (3.1.7.0 R1, the
// owner: "more of insight and ability to jump in and steer"). `pin` (the
// session store) is the one agent the column shows; with none, the Steer box
// at the column's foot talks to the chosen session's main agent (the root of
// its tree), so the steer is always at hand. A "steer" on a line's tag or a
// map node pins that agent and puts the keyboard in that box; outside Session
// it opens the Agent panel's box instead (Fleet keeps its own Steer).
import { useMemo } from "react";
import { studio } from "../../lib/store";
import { layoutStore, patchPanel } from "../../lib/workspace/persist";
import { openAgentPanel, select } from "../fleet/actions";
import { focusSteer } from "../fleet/Steer";
import { fleet, findAgent, keyOf, localId, treeOf, useFleet, type FleetState, type Scope } from "../fleet/store";
import type { AgentKey, AgentRef } from "../fleet/types";
import { chosenSession, sess, useSession } from "./store";

/** Show only `key` in the column ("" = every agent); the map selects it too. */
export function pinTo(key: AgentKey): void {
  sess.update(() => ({ pin: key, follow: true }));
  if (key && findAgent(fleet.get(), key)) select(key);
}

/** A tag or a lane: pin its agent, or, when it is the pinned one, show everyone again. */
export function setPin(key: AgentKey): void {
  pinTo(sess.get().pin === key ? "" : key);
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

/** That session's agents in tree order (the agent pick's rows). */
export function useStripAgents(): AgentRef[] {
  const harnesses = useFleet((s) => s.harnesses);
  const scope = useStripScope();
  return useMemo(() => {
    const h = harnesses.find((x) => x.id === scope.harness);
    const ss = h?.sessions.find((x) => x.session_id === scope.session);
    return h && ss ? treeOf(ss.agents || []).map(({ a, depth }) => ({ key: keyOf(h.id, ss.session_id, a.agent_id), h, s: ss, a, depth })) : [];
  }, [harnesses, scope]);
}

export type SteerTo = { key: AgentKey; ref: AgentRef | null; main: boolean };

/** The pinned agent, else the chosen session's main agent; `main` marks the root of its tree. */
export function steerTarget(s: FleetState, pin: AgentKey): SteerTo {
  if (pin) {
    const ref = findAgent(s, pin);
    return { key: pin, ref, main: !!ref && !ref.a.parent };
  }
  const ss = chosenSession(s);
  if (!ss) return { key: "", ref: null, main: true };
  const root = (ss.agents || []).find((a) => !a.parent) || (ss.agents || [])[0];
  const key = keyOf(localId(s), ss.session_id, root?.agent_id || "main");
  return { key, ref: findAgent(s, key), main: true };
}

export function useSteerTarget(): SteerTo {
  const pin = useSession((s) => s.pin);
  const harnesses = useFleet((s) => s.harnesses);
  const scope = useFleet((s) => s.scope);
  return useMemo(() => steerTarget({ ...fleet.get(), harnesses, scope }, pin), [pin, harnesses, scope]);
}
