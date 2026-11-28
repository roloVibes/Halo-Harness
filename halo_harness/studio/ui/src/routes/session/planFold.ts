// 3.6.0.23 PV: the person's fold of the plan under Session's head (FeedPlan.tsx), kept for this browser the way the
// page keeps a pick (lib/store.ts writeLocal: a click is the choice, no Apply). Folded or not, the chip stays.
// PV after the first CI run: the list is CLOSED until the person opens it (the default); "0" keeps it open, "1" (the
// key's old value, written by a fold before) keeps it closed, so a browser that holds the old key keeps its choice.
import { createStore, useStore, writeLocal } from "../../lib/store";

const KEY = "halo.studio.session-plan-folded";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) !== "0";
  } catch {
    return true; // a private window: nothing remembered, closed
  }
}

const fold = createStore<{ folded: boolean }>({ folded: read() });
export const usePlanFolded = (): boolean => useStore(fold, (s) => s.folded);

export function togglePlanFold(): void {
  const folded = !fold.get().folded;
  fold.update(() => ({ folded }));
  writeLocal(KEY, folded ? "1" : "0");
}
