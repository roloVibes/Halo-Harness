// The "Run a goal" form (3.4.0.0 D; 3.6.0.0 R5: in the Map's drawer, crew/run/door.ts openGoal): closed on load, opened
// only by a click -- the Map bar's Run a goal, the palette's "Agents: Run a goal", History's "Run it again" (`form`: that
// run's goal filled in), the Pack Manager's Run <workflow> (orchestra/workflowRun.ts fills the workflow's form instead)
// -- and closed by its x, Esc, or a run that started. `seed` re-reads the form each time it opens.
import { createStore, useStore } from "../../../lib/store";
import type { RunForm } from "../../orchestra/sync";
import { startOrchestra } from "../../orchestra/sync";
import { history } from "../live/historyStore";

export type GoalForm = Partial<RunForm>;
type State = { open: boolean; seed: number; form: Partial<RunForm> | null };

export const goal = createStore<State>({ open: false, seed: 0, form: null });
export const useGoal = <S,>(pick: (s: State) => S): S => useStore(goal, pick);

/** 3.6.0.0 R4b: the goal form open where it is drawn (the Map's drawer), without going to Live. */
export function openGoalHere(form?: Partial<RunForm>): void {
  startOrchestra();
  goal.update((s) => ({ open: true, seed: s.seed + 1, form: form || null }));
  history.update((s) => (s.open ? { open: false, page: null, report: null, reportError: "" } : {})); // one drawer at a time
}

export function closeGoal(): void {
  goal.update((s) => (s.open ? { open: false, form: null } : {}));
}

export function toggleGoal(): void {
  if (goal.get().open) closeGoal();
  else openGoalHere();
}
