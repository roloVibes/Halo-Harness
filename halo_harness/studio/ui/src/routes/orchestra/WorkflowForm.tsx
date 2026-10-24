// The new-run form for a pack's workflow (3.2.0.0 R6, workflowRun.ts): what
// the Start view shows instead of the goal form while a workflow is filled
// in -- its ref and description, its stages in order, one field per input
// (its type, required or its default, its help), the MODEL select, Run, and
// "a blank goal instead". The workflow writes its own goal (WHAT YOU WANT,
// DONE WHEN, STOP WHEN, the files and the test) when it compiles.
import { useState } from "react";
import { Button, Field } from "../../lib/ui";
import { useHelpGroup } from "../../lib/fieldHelp";
import { ModelSelect } from "../shared/ModelSelect";
import { clearWorkflow, setInput, startWorkflow, useWfRun } from "./workflowRun";
import { useOrch } from "./store";

export function WorkflowForm() {
  const wf = useWfRun((s) => s.wf);
  const values = useWfRun((s) => s.values);
  const live = useOrch((s) => (s.data?.live ? s.runId : ""));
  const [model, setModel] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const help = useHelpGroup("model_select");
  if (!wf) return null;
  const go = async () => {
    setBusy(true);
    setProblems(await startWorkflow(model));
    setBusy(false);
  };
  const why = live ? `Run ${live} is live: stop it or wait for its report` : "";
  return (
    <form className="og-form og-goal-form og-goal-start" onSubmit={(e) => (e.preventDefault(), void go())} data-testid="orchestra-workflow-form">
      <div className="glance-kicker mono">WORKFLOW</div>
      <p className="og-wf-ref mono" data-testid="orchestra-workflow-ref">{wf.ref}</p>
      <p className="muted">{wf.description}</p>
      <p className="mono muted" data-testid="orchestra-workflow-stages">stages: {wf.stages.join(" -> ")}</p>
      {wf.inputs.map((i) => (
        <Field key={i.name} label={`${i.name.toUpperCase()} (${i.type}${i.required ? ", required" : ""})`} hint={i.description || undefined}>
          {(id) => (
            <input id={id} className="input mono" value={values[i.name] ?? ""} onChange={(e) => setInput(i.name, e.target.value)}
                   placeholder={i.required ? "required" : i.default !== null && i.default !== undefined ? `default ${String(i.default)}` : "optional"}
                   data-testid="orchestra-workflow-input" data-key={i.name} />
          )}
        </Field>
      ))}
      <ModelSelect label="MODEL" hint={help.orchestra} value={model} onPick={setModel} testid="orchestra-workflow-model" inherit={{ label: "each stage's bio", model: "" }} />
      {problems.length > 0 && (
        <ul className="og-problems" role="alert" data-testid="orchestra-workflow-problems">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      <div className="og-actions fl-actions">
        <Button variant="primary" type="submit" disabled={busy || !!why} title={why || "Compile it (halo workflow run) and start the run"} data-testid="orchestra-workflow-run">
          Run
        </Button>
        <button type="button" className="og-link mono" onClick={clearWorkflow} data-testid="orchestra-workflow-clear">
          a blank goal instead
        </button>
      </div>
    </form>
  );
}
