// The workflow picker under the goal form on Orchestra's Start view (3.2.1.0
// R2): with no workflow filled in, a select "or run a pack's workflow" lists
// the workflows of the packs that run here (GET pack/manager, read once, then
// again on each pack_changed frame); a pick fills in the same form the Pack
// Manager's Run <workflow> does (workflowRun.ts `runWorkflow`), whose Run
// compiles it as `halo workflow run` does. No running pack with a workflow:
// no select.
import { useEffect } from "react";
import { Field } from "../../lib/ui";
import { startManager, useMgr } from "../packs/manager/store";
import type { PackWorkflow } from "../packs/manager/types";
import { runWorkflow } from "./workflowRun";

export function WorkflowPicker() {
  const packs = useMgr((s) => s.data?.packs);
  useEffect(() => startManager(), []);
  const flows: PackWorkflow[] = (packs || []).filter((p) => p.running).flatMap((p) => p.workflows || []);
  if (!flows.length) return null;
  const pick = (ref: string) => {
    const wf = flows.find((w) => w.ref === ref);
    if (wf) runWorkflow(wf);
  };
  return (
    <div className="og-wf-pick" data-testid="orchestra-workflow-picker">
      <Field label="OR RUN A PACK'S WORKFLOW" hint="The workflows of the packs that run here: a pick fills in its form (its inputs, then Run).">
        {(id) => (
          <select id={id} className="input mono" value="" onChange={(e) => pick(e.target.value)} data-testid="orchestra-workflow-pick">
            <option value="">or run a pack's workflow...</option>
            {flows.map((w) => (
              <option key={w.ref} value={w.ref}>
                {w.ref}
                {w.description ? ` -- ${w.description}` : ""}
              </option>
            ))}
          </select>
        )}
      </Field>
    </div>
  );
}
