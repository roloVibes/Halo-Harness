// The workflow picker under the goal form on Orchestra's Start view (3.2.1.0
// R2): with no workflow filled in, a select "or run a pack's workflow" lists
// the workflows of the packs that run here (GET pack/manager, read once, then
// again on each pack_changed frame); a pick fills in the same form the Pack
// Manager's Run <workflow> does (workflowRun.ts `runWorkflow`), whose Run
// compiles it as `halo workflow run` does. No running pack with a workflow:
// no select. 3.6.0.6 P: under it, the head "Workflows" lists every crew workflow a session runs by name (an enabled
// pack's with its tag, yours, this project's), each with the one Run it (routes/crew/flows/RunFlow.tsx).
import { useEffect } from "react";
import { Field } from "../../lib/ui";
import { loadFlows, useFlows } from "../crew/flows/flowStore";
import { RunFlow } from "../crew/flows/RunFlow";
import { RUN_HEAD, runnable } from "../crew/flows/runWords";
import { scopeTag } from "../crew/scopeTag";
import { startManager, useMgr } from "../packs/manager/store";
import type { PackWorkflow } from "../packs/manager/types";
import { runWorkflow } from "./workflowRun";

function CrewFlows() {
  const all = useFlows((s) => s.flows);
  useEffect(() => { void loadFlows(); }, []);
  const rows = runnable(all);
  if (!rows.length) return null;
  return (
    <div className="og-wf-pick rf-list" data-testid="goal-flows">
      <span className="cw-label mono">{RUN_HEAD}</span>
      {rows.map((r) => (
        <div key={`${r.scope}:${r.name}`} className="rf-item" data-testid="goal-flow" data-name={r.name} data-scope={r.scope}>
          <span className="cw-item-head"><b className="cw-item-name mono">{r.name}</b>
            {scopeTag(r.scope, r.name) && <span className="cw-tag" data-testid="goal-flow-tag">{scopeTag(r.scope, r.name)}</span>}</span>
          <RunFlow name={r.name} scope={r.scope} problems={r.problems} where="goal" />
        </div>
      ))}
    </div>
  );
}

export function WorkflowPicker() {
  return (<><PackPicker /><CrewFlows /></>);
}

function PackPicker() {
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
