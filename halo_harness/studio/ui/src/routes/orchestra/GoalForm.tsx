// The goal form (GoalPanel's Expand face): WHAT YOU WANT, DONE WHEN, STOP
// WHEN, then the workers, the return cap, the test, the files, who plays the
// parts and the model; Run and Dry run post it (POST orchestra/run).
import { useEffect, useState } from "react";
import { Button, Field } from "../../lib/ui";
import { orch, useOrch } from "./store";
import { startRun, type RunForm } from "./sync";

const EMPTY: RunForm = {
  what: "",
  done_when: "",
  stop_when: "",
  workers: 5,
  return_cap: 2,
  test: "",
  files: [],
  lineup: "",
  lead: "main",
  worker: "subagent",
  model: "",
};

function fromGoal(): RunForm {
  const g = orch.get().data?.goal;
  return g ? { ...EMPTY, ...g, files: [...(g.files || [])], model: "" } : { ...EMPTY };
}

function Text({ label, value, set, rows = 2, hint }: { label: string; value: string; set: (v: string) => void; rows?: number; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => <textarea id={id} className="input og-text" rows={rows} value={value} onChange={(e) => set(e.target.value)} />}
    </Field>
  );
}

function Line({ label, value, set, mono }: { label: string; value: string; set: (v: string) => void; mono?: boolean }) {
  return (
    <Field label={label}>
      {(id) => <input id={id} className={"input" + (mono ? " mono" : "")} value={value} onChange={(e) => set(e.target.value)} />}
    </Field>
  );
}

function Num({ label, value, set, min, max }: { label: string; value: number; set: (v: number) => void; min: number; max: number }) {
  return (
    <Field label={label}>
      {(id) => (
        <input
          id={id}
          className="input mono"
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(e) => {
            const n = parseInt(e.target.value, 10);
            if (!Number.isNaN(n)) set(n);
          }}
        />
      )}
    </Field>
  );
}

export function GoalForm() {
  const runId = useOrch((s) => s.runId);
  const live = useOrch((s) => !!s.data?.live);
  const [form, setForm] = useState<RunForm>(fromGoal);
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => setForm(fromGoal()), [runId]);
  const set = <K extends keyof RunForm>(k: K) => (v: RunForm[K]) => setForm((f) => ({ ...f, [k]: v }));
  const go = async (dry: boolean) => {
    setBusy(true);
    setProblems(await startRun(form, dry));
    setBusy(false);
  };
  return (
    <form className="og-form" onSubmit={(e) => (e.preventDefault(), void go(false))}>
      <Text label="WHAT YOU WANT" value={form.what} set={set("what")} rows={3} />
      <Text label="DONE WHEN" value={form.done_when} set={set("done_when")} hint="what the gate checks" />
      <Text label="STOP WHEN" value={form.stop_when} set={set("stop_when")} hint="when the run gives up" />
      <div className="og-form-row">
        <Num label="WORKERS" value={form.workers} set={set("workers")} min={1} max={50} />
        <Num label="RETURN CAP" value={form.return_cap} set={set("return_cap")} min={0} max={20} />
      </div>
      <Line label="TEST COMMAND" value={form.test} set={set("test")} mono />
      <Line label="FILES (comma separated, from the repo root)" value={form.files.join(", ")} set={(v) => set("files")(v.split(",").map((f) => f.trim()).filter(Boolean))} mono />
      <div className="og-form-row">
        <Line label="LINEUP" value={form.lineup} set={set("lineup")} />
        <Line label="MODEL" value={form.model} set={set("model")} mono />
      </div>
      <div className="og-form-row">
        <Line label="LEAD ROLE" value={form.lead} set={set("lead")} />
        <Line label="WORKER ROLE" value={form.worker} set={set("worker")} />
      </div>
      {problems.length > 0 && (
        <ul className="og-problems" role="alert">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      <div className="og-actions">
        <Button variant="primary" type="submit" disabled={busy || live} title={live ? "A run is live: stop it or wait for its report" : "Start the run"}>
          Run
        </Button>
        <Button onClick={() => void go(true)} disabled={busy || live} title="Ask the lead for the split only: nothing is claimed">
          Dry run
        </Button>
        <Button variant="ghost" onClick={() => setForm({ ...EMPTY })} disabled={busy}>
          Clear
        </Button>
      </div>
    </form>
  );
}
