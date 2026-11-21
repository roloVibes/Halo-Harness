// Run it (3.6.0.6 P, the owner's point 31: "pack workflows should be launchable from any studio view that can see
// them"): the words, what is offered for a row and the request -- pure, so tests/test_run_flow_ui.py runs it in node.
// RunFlow.tsx is the ONE control that starts a real run of a crew workflow (POST crew/run: a new session runs it by
// name on its own step runner, crew/flow_run.py); runFlowStore.ts holds the open form (this file is runWords.ts: RunFlow.tsx and a runFlow.ts would be one file on Windows and macOS). Every view that shows a
// workflow offers it the same way: Agents -> 2 · Workflows, the Run a goal drawer, the Pack Manager, a pack's
// section, a workflow's box on the Map, the palette.
import type { Scope } from "../types";

export const RUN_IT = "Run it";
export const RUN = "Run";
export const CANCEL = "Cancel";
export const WATCH = "Watch it in Live";
/** The Run a goal drawer's head over the workflows it can run. */
export const RUN_HEAD = "Workflows";
/** The palette's one command (routes/crew/flows/commands.ts). */
export const RUN_A_WORKFLOW = "Run a workflow";
/** The palette's list while the workflows are still being read (a pick made at once on a slow first read). */
export const READING = "Reading the workflows...";
export const RUN_PATH = "crew/run";

/** The line the form says before Run, word for word (what it does, what it may change, what it costs). */
export const runLine = (folder: string): string =>
  `Starts a new session in ${folder} that runs this workflow's steps on your models. It can change files there. Cost and time depend on the models its steps use.`;

/** The receipt in the form's place once the run started. */
export const startedLine = (id: string): string => `Started: session ${id}.`;

export type RunRow = { name: string; scope: Scope | string; problems?: string[] };

/** What a row is offered: `show` -- a session runs it by name (an enabled pack's, yours, this project's; one that
 *  ships with Halo is copied first, crew/flow_door.py); `off` -- its first problem, said on hover, "" when it can run. */
export function offer(r: RunRow): { show: boolean; off: string } {
  const show = r.scope === "pack" || r.scope === "yours" || r.scope === "project";
  return { show, off: show ? (r.problems || [])[0] || "" : "" };
}

/** The rows a view lists under "Run it" (the palette's list, the goal drawer's head). */
export const runnable = <R extends RunRow>(rows: R[]): R[] => rows.filter((r) => offer(r).show);

/** POST crew/run's body. */
export const runBody = (name: string, task: string): { name: string; task: string } => ({ name, task: task.trim() });

/** Run is on once a task is typed and nothing is under way. */
export const canRun = (task: string, busy: boolean): boolean => !!task.trim() && !busy;
