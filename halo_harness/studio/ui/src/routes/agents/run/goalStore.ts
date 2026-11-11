// Live's "Run a goal" panel (3.4.0.0 D "the runs fold"; Runs' Start screen before): closed on load, opened only by a
// click -- the button on Live's bar, the palette's "Agents: Run a goal", History's "Run it again" (`form`: that run's
// goal filled in), the Pack Manager's Run <workflow> (orchestra/workflowRun.ts fills the workflow's form instead) --
// and closed by its x, Esc, or a run that started. `seed` re-reads the form each time it opens.
import { createStore, goSection, useStore } from "../../../lib/store";
import type { RunForm } from "../../orchestra/sync";
import { startOrchestra } from "../../orchestra/sync";
import { history } from "../live/historyStore";

type State = { open: boolean; seed: number; form: Partial<RunForm> | null };

export const goal = createStore<State>({ open: false, seed: 0, form: null });
export const useGoal = <S,>(pick: (s: State) => S): S => useStore(goal, pick);

/** Live with the goal panel open (with `form`, those fields filled in). */
export function openGoal(form?: Partial<RunForm>): void {
  startOrchestra();
  goSection("agents", "live");
  goal.update((s) => ({ open: true, seed: s.seed + 1, form: form || null }));
  history.update((s) => (s.open ? { open: false, page: null, report: null, reportError: "" } : {})); // one drawer at a time
}

export function closeGoal(): void {
  goal.update((s) => (s.open ? { open: false, form: null } : {}));
}

export function toggleGoal(): void {
  if (goal.get().open) closeGoal();
  else openGoal();
}
