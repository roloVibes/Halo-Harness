// Agents -> Live's scope and its pick (3.3.16.0 R2 "the Fleet fold": a machine's agents in Agents). The scope is
// **this halo** (the session picker over this harness's sessions, one session's tree) or **fleet** (every harness
// as a machine, its sessions under it, their agents under those; a mission's parts under the machine they run on).
// Unset, it is fleet while more than one harness is paired and this halo otherwise; `?scope=fleet|here`, `?mode=fleet`,
// the bar's switch and `F` (Shift+F) while the canvas has the keyboard set it (`f` there still fits the tree). The pick is what the inspector says something about: nothing
// (the fleet at a glance), a machine, an agent (the fleet store's `selected` too: Steer, the Pip, J / K follow it), a
// session or a mission part.
import { urlScope, type LiveScope } from "../../../lib/agentsDoor";
import { createStore, useStore } from "../../../lib/store";
import { layoutStore, patchPanel } from "../../../lib/workspace/persist";
import { fleet, useFleet } from "../../fleet/store";

export type PickKind = "" | "machine" | "session" | "agent" | "part";
export type LivePick = { kind: PickKind; id: string };
/** `page`: the one block a machine's summary edits ("" = the summary; R1b's one block per page). */
type LiveState = { scope: LiveScope | ""; pick: LivePick; page: string };

const NONE: LivePick = { kind: "", id: "" };
export const live = createStore<LiveState>({ scope: urlScope(), pick: NONE, page: "" });

/** The scope Live draws: the one chosen, else fleet while another harness is here; this halo while the fleet pack
 *  is off (3.4.0.0 C). */
export function scopeOf(chosen: LiveScope | "", harnesses: number, pack = true): LiveScope {
  if (!pack) return "here";
  return chosen || (harnesses > 1 ? "fleet" : "here");
}

export function useLiveScope(): LiveScope {
  const chosen = useStore(live, (s) => s.scope);
  const n = useFleet((s) => s.harnesses.length);
  const pack = useFleet((s) => s.pack);
  return scopeOf(chosen, n, pack);
}

export function liveScope(): LiveScope {
  return scopeOf(live.get().scope, fleet.get().harnesses.length, fleet.get().pack);
}

export function setScope(scope: LiveScope): void {
  live.update((s) => (s.scope === scope ? {} : { scope }));
}

export function toggleScope(): void {
  setScope(liveScope() === "fleet" ? "here" : "fleet");
}

export function useLivePick(): LivePick {
  return useStore(live, (s) => s.pick);
}

/** The inspector says something about this (an agent's pick is also fleet.selected: liveModel.ts selectLive); a pick
 *  opens the inspector when it is a strip (as a card's click does on Cast). */
export function pickLive(kind: PickKind, id: string): void {
  live.update((s) => (s.pick.kind === kind && s.pick.id === id ? {} : { pick: { kind, id }, page: "" }));
  if (kind && layoutStore("roles").get().layout?.["roles-inspector"]?.collapsed) patchPanel("roles", "roles-inspector", { collapsed: false, face: "detail" }, false);
}

export function clearPick(): void {
  live.update((s) => (s.pick.kind ? { pick: NONE, page: "" } : {}));
}

export const useMachinePage = (): string => useStore(live, (s) => s.page);

/** A machine's summary on one block (`specs`, `caps`), or back on the summary (""). */
export function setMachinePage(page: string): void {
  live.update((s) => (s.page === page ? {} : { page }));
}
