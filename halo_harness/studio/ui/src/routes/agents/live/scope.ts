// Agents -> Live's pick: what the inspector says something about -- nothing, an agent (the live store's `selected`
// too: Steer, the Pip, J / K follow it) or a session; 3.4.0.0 D a goal run's lead or one of its lanes
// (routes/agents/run/RunInspector.tsx). 3.5.0.0: Live draws this halo's sessions only (the fleet scope left with Fleet).
import { createStore, useStore } from "../../../lib/store";
import { layoutStore, patchPanel } from "../../../lib/workspace/persist";

export type PickKind = "" | "session" | "agent" | "run" | "lane"; // 3.4.0.0 D: a goal run's lead (`<run>`), a lane (`<run>:<n>`)
export type LivePick = { kind: PickKind; id: string };
type LiveState = { pick: LivePick; page: string };

const NONE: LivePick = { kind: "", id: "" };
export const live = createStore<LiveState>({ pick: NONE, page: "" });

export function useLivePick(): LivePick {
  return useStore(live, (s) => s.pick);
}

/** The inspector says something about this (an agent's pick is also fleet.selected: liveModel.ts selectLive); a pick
 *  opens the inspector when it is a closed drawer (as a card's click does on Cast). */
export function pickLive(kind: PickKind, id: string): void {
  live.update((s) => (s.pick.kind === kind && s.pick.id === id ? {} : { pick: { kind, id }, page: "" }));
  if (kind && layoutStore("roles").get().layout?.["roles-inspector"]?.collapsed) patchPanel("roles", "roles-inspector", { collapsed: false, face: "detail" }, false);
}

export function clearPick(): void {
  live.update((s) => (s.pick.kind ? { pick: NONE, page: "" } : {}));
}

export const useInspectorPage = (): string => useStore(live, (s) => s.page);

/** The picked thing's inspector on one block (a goal run's pages), or back on its summary (""). */
export function setInspectorPage(page: string): void {
  live.update((s) => (s.page === page ? {} : { page }));
}

