// 3.6.0.23 PV: the person's fold of the plan under Session's head (FeedPlan.tsx), kept for this browser the way the
// page keeps a pick (lib/store.ts writeLocal: a click is the choice, no Apply). Folded or not, the chip stays.
import { createStore, useStore, writeLocal } from "../../lib/store";

const KEY = "halo.studio.session-plan-folded";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false; // a private window: nothing remembered
  }
}

const fold = createStore<{ folded: boolean }>({ folded: read() });
export const usePlanFolded = (): boolean => useStore(fold, (s) => s.folded);

export function togglePlanFold(): void {
  const folded = !fold.get().folded;
  fold.update(() => ({ folded }));
  writeLocal(KEY, folded ? "1" : null);
}
