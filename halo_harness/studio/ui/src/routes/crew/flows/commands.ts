// The palette's Run a workflow (3.6.0.6 P): ONE command; Enter on it lists the workflows a session runs by name (an
// enabled pack's with its tag, yours, this project's: GET crew/workflows), and a pick opens the same Run it form
// (RunDock.tsx) in the view he is in. One with a problem is listed off, its hint the problem.
import { scopeTag } from "../scopeTag";
import { flows, loadFlows } from "./flowStore";
import { DOCK } from "./RunDock";
import { RUN_A_WORKFLOW, offer, runnable } from "./runWords";
import { openRun } from "./runFlowStore";

export type FlowCommand = { id: string; group: string; label: string; hint?: string; disabled?: boolean; run: () => void;
                            list?: () => FlowCommand[] };

export function flowCommands(): FlowCommand[] {
  if (!flows.get().loaded) void loadFlows();
  const list = (): FlowCommand[] => runnable(flows.get().flows).map((r) => {
    const off = offer(r).off;
    return { id: "run-flow-" + r.name, group: RUN_A_WORKFLOW, label: r.name, hint: off || scopeTag(r.scope, r.name) || undefined,
             disabled: !!off, run: () => void openRun(DOCK, r.name) };
  });
  return [{ id: "run-flow", group: "Agents", label: RUN_A_WORKFLOW, run: () => undefined, list }];
}
