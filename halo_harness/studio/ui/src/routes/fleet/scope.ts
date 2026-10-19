// The Fleet stores' one scope (3.1.4.0 R2): `fleet.scope` = {harness?, session?}.
// The Fleet section leaves it empty (the whole fleet, as before); the Session
// section (routes/session/store.ts) sets this harness, and the session chosen,
// while it shows, and clears it when you leave. Map, Activity (the log and the
// timeline lanes), Attention and the cost figures read through these
// selectors, so each stays one component: the map draws the harness in scope
// (every session on it), the log, the lanes and the Cost panel the chosen
// session (else every session of that harness), Attention that harness's rows.
// The rail's Fleet tree and Live Roles never read it: they show everything.
import { useMemo } from "react";
import { usePanels, type AttnRow, type LogLine } from "./pstore";
import { allAgents, counts, fleet, useFleet, type Counts, type FleetState, type Scope } from "./store";
import type { AgentRef, Harness } from "./types";

export const useScope = (): Scope => useFleet((s) => s.scope);

/** True while a section narrows the Fleet panels (Session). */
export const isScoped = (scope: Scope = fleet.get().scope): boolean => !!scope.harness;

/** The harnesses in scope (the map's boxes): every one, or the scope's harness with every session on it. */
export function harnessesIn(harnesses: Harness[], scope: Scope): Harness[] {
  return scope.harness ? harnesses.filter((h) => h.id === scope.harness) : harnesses;
}

/** The same, narrowed to the chosen session (the log, the lanes, the cost). */
export function sessionsIn(harnesses: Harness[], scope: Scope): Harness[] {
  const hs = harnessesIn(harnesses, scope);
  return scope.session ? hs.map((h) => ({ ...h, sessions: (h.sessions || []).filter((s) => s.session_id === scope.session) })) : hs;
}

/** Every agent in scope, in tree order (`withSession`: of the chosen session only). */
export function scopedAgents(s: FleetState, withSession = false): AgentRef[] {
  return allAgents({ ...s, harnesses: (withSession ? sessionsIn : harnessesIn)(s.harnesses, s.scope) });
}

/** A log line (or a lane) inside the scope. */
export const lineIn = (scope: Scope) => (l: Pick<LogLine, "harness" | "session_id">): boolean =>
  (!scope.harness || l.harness === scope.harness) && (!scope.session || l.session_id === scope.session);

/** An attention row of the harness in scope. */
export const rowIn = (scope: Scope) => (r: AttnRow): boolean => !scope.harness || r.harness === scope.harness;

export function useScopedHarnesses(withSession = false): Harness[] {
  const harnesses = useFleet((s) => s.harnesses);
  const scope = useScope();
  return useMemo(() => (withSession ? sessionsIn : harnessesIn)(harnesses, scope), [harnesses, scope, withSession]);
}

/** The counts of the harnesses in scope (the map's toolbar, its glance, the Activity glance). */
export function useScopedCounts(): Counts {
  const hs = useScopedHarnesses();
  return useMemo(() => counts({ harnesses: hs }), [hs]);
}

/** The attention rows in scope, and how many wait (the watcher's live count when nothing narrows them). */
export function useScopedAttention(): { rows: AttnRow[]; count: number } {
  const rows = usePanels((s) => s.attention);
  const live = usePanels((s) => s.attnCount);
  const scope = useScope();
  return useMemo(() => {
    const mine = scope.harness ? rows.filter(rowIn(scope)) : rows;
    return { rows: mine, count: scope.harness ? mine.length : live ?? rows.length };
  }, [rows, live, scope]);
}
