// The goal form (3.4.0.0 D: in Live's Run a goal panel, routes/agents/run/GoalDrawer.tsx; Runs' Start view and Goal
// panel before): WHAT YOU WANT, DONE WHEN, STOP WHEN with examples, the files (the shared files) and the test (the
// gate's), the budget (workers, return cap) and the lineup, the MODEL (its first option "the lineup's (<the lead's
// model>)"), Review the plan first, then who plays the parts under a disclosure; what it will do, what it may cost and
// where it writes (GoalSays.tsx) right above Run and Dry run, which post it (POST orchestra/run). LINEUP offers every
// lineup by name (shared/LineupField.tsx); the three goal boxes are the one text box (three lines at the least).
import { useEffect, useState } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { useStore } from "../../lib/store";
import { Button, Field, Icon } from "../../lib/ui";
import { LineupField } from "../shared/LineupField";
import { ModelSelect } from "../shared/ModelSelect";
import { useResolved } from "../shared/resolve";
import { GoalSays } from "../agents/run/GoalSays";
import { useOrch } from "./store";
import { lastStarted, lineupTook, startRun, type RunForm } from "./sync";

const EMPTY: RunForm = { what: "", done_when: "", stop_when: "", workers: 5, return_cap: 2, test: "", files: [], lineup: "", lead: "main", worker: "subagent", model: "", review: false };

const EXAMPLE = {
  what: "e.g. Add input checks to every public function in basket.py",
  done_when: "e.g. python -m pytest tests/test_basket.py passes and every function rejects bad input.",
  stop_when: "e.g. a part fails the gate twice, or a change reaches outside basket.py.",
  files: "e.g. basket.py, prices.py",
  test: "e.g. python -m pytest -q",
};

function fromSeed(initial: Partial<RunForm> | null): RunForm {
  return initial ? { ...EMPTY, ...initial, files: [...(initial.files || [])] } : { ...EMPTY };
}

type Setter<K extends keyof RunForm> = (v: RunForm[K]) => void;

function Text({ label, value, set, hint, example }: { label: string; value: string; set: (v: string) => void; hint?: string; example: string }) {
  return (
    <Field label={label} hint={hint} multiline={{ value, placeholder: example, title: hint, onChange: (e) => set(e.target.value) }} />
  );
}

function Line({ label, value, set, mono, example }: { label: string; value: string; set: (v: string) => void; mono?: boolean; example?: string }) {
  return (
    <Field label={label}>
      {(id) => <input id={id} className={"input" + (mono ? " mono" : "")} value={value} placeholder={example} onChange={(e) => set(e.target.value)} />}
    </Field>
  );
}

function Num({ label, value, set, min, max, title }: { label: string; value: number; set: (v: number) => void; min: number; max: number; title: string }) {
  return (
    <Field label={label}>
      {(id) => (
        <input id={id} className="input mono" type="number" min={min} max={max} value={value} title={title} onChange={(e) => {
          const n = parseInt(e.target.value, 10);
          if (!Number.isNaN(n)) set(n);
        }} />
      )}
    </Field>
  );
}

type Props = { initial: Partial<RunForm> | null; seed: number; onStarted: (id: string, dry: boolean) => void };

export function GoalForm({ initial, seed, onStarted }: Props) {
  const runId = useOrch((s) => s.runId);
  const live = useOrch((s) => (s.data?.live ? s.runId : ""));
  const [form, setForm] = useState<RunForm>(() => fromSeed(initial));
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const lead = useResolved(form.lead || "main"); // what the run's lead resolves to without a MODEL: the role table, else the default
  const took = useStore(lineupTook, (s) => (s.run && s.run === runId ? s.test : "")); // 3.2.1.0 R1: the lineup's acceptance.test
  const help = useHelpGroup("model_select");
  useEffect(() => {
    setForm(fromSeed(initial));
    setProblems([]);
  }, [seed]); // eslint-disable-line react-hooks/exhaustive-deps -- a new opening of the panel, not each render
  const set = <K extends keyof RunForm>(k: K): Setter<K> => (v) => setForm((f) => ({ ...f, [k]: v }));
  const go = async (dry: boolean) => {
    setBusy(true);
    const got = await startRun(form, dry);
    setProblems(got);
    setBusy(false);
    if (!got.length) onStarted(lastStarted.id, dry);
  };
  const why = live ? `Run ${live} is live: stop it or wait for its report` : "";
  const review = (
    <label className="og-switch mono" title="The run stops after the lead's split: the plan waits for you on Live (Review the plan on its lead), then Approve and run (or Reject)">
      <input type="checkbox" checked={!!form.review} onChange={(e) => set("review")(e.target.checked)} data-testid="orchestra-review" />
      Review the plan first
    </label>
  );
  return (
    <form className="og-form og-goal-form og-goal-start" onSubmit={(e) => (e.preventDefault(), void go(false))} data-testid="orchestra-goal-form">
      <Text label="WHAT YOU WANT" value={form.what} set={set("what")} example={EXAMPLE.what} />
      <Text label="DONE WHEN" value={form.done_when} set={set("done_when")} example={EXAMPLE.done_when} hint="what the gate checks before the result lands" />
      <Text label="STOP WHEN" value={form.stop_when} set={set("stop_when")} example={EXAMPLE.stop_when} hint="when the run gives up" />
      <div className="og-form-row">
        <Line label="SHARED FILES (comma separated)" value={form.files.join(", ")} set={(v) => set("files")(v.split(",").map((f) => f.trim()).filter(Boolean))} mono example={EXAMPLE.files} />
        <Line label="THE GATE'S TEST" value={form.test} set={set("test")} mono example={EXAMPLE.test} />
      </div>
      {took && <p className="og-took mono muted" data-testid="orchestra-test-from-lineup">test from the lineup: {took}</p>}
      <div className="og-form-row og-form-row3" role="group" aria-label="Budget and lineup">
        <Num label="WORKERS" value={form.workers} set={set("workers")} min={1} max={50} title="How many lanes, one worker each (1 to 50)" />
        <Num label="RETURN CAP" value={form.return_cap} set={set("return_cap")} min={0} max={20} title="How many times the gate may send one part back" />
        <LineupField label="LINEUP" value={form.lineup} set={set("lineup")} example="optional" testid="orchestra-lineup" />
      </div>
      <ModelSelect label="MODEL" hint={help.orchestra} value={form.model} onPick={set("model")} testid="orchestra-model"
                   inherit={{ label: "the lineup's", model: lead?.ref || "" }} />
      <details className="md-support og-more">
        <summary className="mono">who plays the parts ({form.lead} leads, {form.worker} works)</summary>
        <div className="og-form-row">
          <Line label="LEAD ROLE" value={form.lead} set={set("lead")} />
          <Line label="WORKER ROLE" value={form.worker} set={set("worker")} />
        </div>
      </details>
      {review}
      <GoalSays form={form} lead={lead?.ref || ""} />
      {problems.length > 0 && (
        <ul className="og-problems" role="alert">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      <div className="og-actions fl-actions">
        <Button variant="primary" type="submit" disabled={busy || !!why} title={why || "Start the run"} data-testid="orchestra-run">
          Run
        </Button>
        <Button onClick={() => void go(true)} disabled={busy || !!why} title={why || "Ask the lead for the split only: nothing is claimed"}>
          Dry run
        </Button>
        <button type="button" className="icon-btn" onClick={() => setForm({ ...EMPTY })} disabled={busy} title="Clear the form" aria-label="Clear the form">
          <Icon name="reset" />
        </button>
      </div>
    </form>
  );
}
