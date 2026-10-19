// "Watch in Session" (3.1.4.0 R2): where an agent of this harness works --
// a card's agent on the Roles Live tab, a live Orchestra run -- one button
// opens the Session dashboard on its session (store.ts openSession: the
// session chosen, the agent selected). Only for this harness: Session is this
// machine's view; a member's agent stays in Fleet.
import { findAgent, localId, parseKey, useFleet, type FleetState } from "../fleet/store";
import { localSessions, openSession } from "./store";

/** True when `key` is an agent of this harness the Fleet store holds. */
export function useLocalAgent(key: string): boolean {
  return useFleet((s) => !!key && parseKey(key).h === localId(s) && !!findAgent(s, key));
}

/**
 * The live session of an Orchestra run on this harness: of the sessions its
 * holders name (`<sid>/<agent>`: the lead and each lane) or its workers run in
 * (their folder is under the run's), the one that started the run (the
 * workers' parent) when it is live here, else the first worker's; '' for none.
 */
export function runSession(s: FleetState, runId: string, holders: string[]): string {
  const local = localSessions(s);
  const ids = new Set(local.map((x) => x.session_id));
  const named = holders.map((h) => String(h || "").split("/")[0]).filter((sid) => ids.has(sid));
  const workers = local.filter((x) => x.kind === "orchestra-worker" && !!runId && String(x.cwd || "").includes(runId)).map((x) => x.session_id);
  const hits = [...new Set([...named, ...workers])];
  for (const sid of hits) {
    const parent = local.find((x) => x.session_id === sid)?.parent;
    if (parent && ids.has(parent)) return parent;
  }
  return hits[0] || "";
}

export function WatchInSession({ session, agent, testid }: { session?: string; agent?: string; testid: string }) {
  return (
    <button type="button" className="og-link mono watch-session" onClick={() => openSession(agent ? { key: agent } : { session })} data-testid={testid}
            title="Open the Session dashboard on it: its map, its timeline and log, what waits on you, what it costs">
      Watch in Session
    </button>
  );
}
