// The goal form, on the Start view (`start`: a blank goal, room to write) and
// as the Goal panel's full face (the open run in one line over its goal, laid
// out so every field and Run show at the panel's default size): WHAT YOU
// WANT, DONE WHEN, STOP WHEN with examples, the files and the test, the
// budget (workers, return cap) and the lineup, the MODEL (3.1.4.0 R4: the
// model select in plain sight, its first option "the lineup's (<the lead's
// model>)"), then who plays the parts under a disclosure. Run and Dry run
// post it (POST orchestra/run). 3.2.2.0 R6: LINEUP offers every lineup by
// name, the list kept current from disk (shared/LineupField.tsx).
import { useEffect, useState } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { useStore } from "../../lib/store";
import { Button, Field, Icon } from "../../lib/ui";
import { useFleet } from "../fleet/store";
import { runSession, WatchInSession } from "../session/Watch";
import { LineupField } from "../shared/LineupField";
import { ModelSelect } from "../shared/ModelSelect";
import { useResolved } from "../shared/resolve";
import { StateBadge } from "./bits";
import { cost } from "./format";
import { orch, setView, useOrch } from "./store";
import { lineupTook, startRun, stopRun, type RunForm } from "./sync";

const EMPTY: RunForm = { what: "", done_when: "", stop_when: "", workers: 5, return_cap: 2, test: "", files: [], lineup: "", lead: "main", worker: "subagent", model: "", review: false };

const EXAMPLE = {
  what: "e.g. Add input checks to every public function in basket.py, with a clear error for each bad value.",
  done_when: "e.g. python -m pytest tests/test_basket.py passes and every function rejects bad input.",
  stop_when: "e.g. a part fails the gate twice, or a change reaches outside basket.py.",
  files: "e.g. basket.py, prices.py",
  test: "e.g. python -m pytest -q",
};

function fromGoal(): RunForm {
  const g = orch.get().data?.goal;
  return g ? { ...EMPTY, ...g, files: [...(g.files || [])], model: "", review: g.plan === "review" } : { ...EMPTY };
}

type Setter<K extends keyof RunForm> = (v: RunForm[K]) => void;

function Text({ label, value, set, hint, example, tall }: { label: string; value: string; set: (v: string) => void; hint?: string; example: string; tall?: boolean }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => <textarea id={id} className={"input og-text" + (tall ? " og-text-tall" : "")} value={value} placeholder={example} title={hint} onChange={(e) => set(e.target.value)} />}
    </Field>
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

/** The open run in one line: its state and cost (the id on hover), stop while it runs, Watch in Session
 *  while its session is live on this harness (3.1.4.0 R2), and a way to a blank goal. */
function RunLine() {
  const data = useOrch((s) => s.data);
  const holders = data ? [data.run.lead_holder || "", ...data.lanes.map((l) => l.holder)].join(",") : "";
  const watch = useFleet((s) => (data?.live ? runSession(s, data.run.run_id, holders.split(",")) : ""));
  if (!data) return null;
  return (
    <div className="fl-runline og-runline" title={`run ${data.run.run_id}: ${data.goal.what}`}>
      <StateBadge state={data.run.state} />
      <span className="mono">{cost(data.run.cost_usd)}</span>
      {data.live && (
        <button type="button" className="og-link mono" onClick={() => void stopRun()}>
          stop
        </button>
      )}
      {watch && <WatchInSession session={watch} testid="orchestra-watch-session" />}
      <button type="button" className="og-link mono" onClick={() => setView("start")} title="The Start view: a blank goal">
        new run
      </button>
    </div>
  );
}

export function GoalForm({ start }: { start?: boolean }) {
  const runId = useOrch((s) => s.runId);
  const live = useOrch((s) => (s.data?.live ? s.runId : ""));
  const has = useOrch((s) => !!s.data);
  const [form, setForm] = useState<RunForm>(() => (start ? { ...EMPTY } : fromGoal()));
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const lead = useResolved(form.lead || "main"); // what the run's lead resolves to without a MODEL: the role table, else the default
  const took = useStore(lineupTook, (s) => (s.run && s.run === runId ? s.test : "")); // 3.2.1.0 R1: the lineup's acceptance.test
  const help = useHelpGroup("model_select");
  useEffect(() => {
    if (!start) setForm(fromGoal());
  }, [runId, has, start]);
  const set = <K extends keyof RunForm>(k: K): Setter<K> => (v) => setForm((f) => ({ ...f, [k]: v }));
  const go = async (dry: boolean) => {
    setBusy(true);
    setProblems(await startRun(form, dry));
    setBusy(false);
  };
  const why = live ? `Run ${live} is live: stop it or wait for its report` : "";
  // 3.0.9.0 R2: the switch sits by Run on the Start view, under the disclosure on the Goal panel (it keeps its size)
  const review = (
    <label className="og-switch mono" title="The lead's split opens on the plan canvas: edit the lanes, then Approve and run (or Reject)">
      <input type="checkbox" checked={!!form.review} onChange={(e) => set("review")(e.target.checked)} data-testid="orchestra-review" />
      Review the plan before it runs
    </label>
  );
  return (
    <form className={"og-form og-goal-form" + (start ? " og-goal-start" : "")} onSubmit={(e) => (e.preventDefault(), void go(false))} data-testid="orchestra-goal-form">
      {!start && <RunLine />}
      {start && has && (
        <button type="button" className="og-link mono og-copy" onClick={() => setForm(fromGoal())}>
          copy the goal of run {runId}
        </button>
      )}
      <Text label="WHAT YOU WANT" value={form.what} set={set("what")} example={EXAMPLE.what} tall={start} />
      <Text label="DONE WHEN" value={form.done_when} set={set("done_when")} example={EXAMPLE.done_when} hint={start ? "what the gate checks before the result lands" : undefined} />
      <Text label="STOP WHEN" value={form.stop_when} set={set("stop_when")} example={EXAMPLE.stop_when} hint={start ? "when the run gives up" : undefined} />
      <div className="og-form-row">
        <Line label="FILES (comma separated)" value={form.files.join(", ")} set={(v) => set("files")(v.split(",").map((f) => f.trim()).filter(Boolean))} mono example={EXAMPLE.files} />
        <Line label="TEST COMMAND" value={form.test} set={set("test")} mono example={EXAMPLE.test} />
      </div>
      {took && <p className="og-took mono muted" data-testid="orchestra-test-from-lineup">test from the lineup: {took}</p>}
      <div className="og-form-row og-form-row3" role="group" aria-label="Budget and lineup">
        <Num label="WORKERS" value={form.workers} set={set("workers")} min={1} max={50} title="How many lanes, one worker each (1 to 50)" />
        <Num label="RETURN CAP" value={form.return_cap} set={set("return_cap")} min={0} max={20} title="How many times the gate may send one part back" />
        <LineupField label="LINEUP" value={form.lineup} set={set("lineup")} example="optional" testid="orchestra-lineup" />
      </div>
      <ModelSelect label="MODEL" hint={help.orchestra} value={form.model} onPick={set("model")} testid="orchestra-model" compact={!start}
                   inherit={{ label: "the lineup's", model: lead?.ref || "" }} />
      <details className="md-support og-more">
        <summary className="mono">who plays the parts ({form.lead} leads, {form.worker} works)</summary>
        <div className="og-form-row">
          <Line label="LEAD ROLE" value={form.lead} set={set("lead")} />
          <Line label="WORKER ROLE" value={form.worker} set={set("worker")} />
        </div>
        {!start && review}
      </details>
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
        {start && review}
        <button type="button" className="icon-btn" onClick={() => setForm({ ...EMPTY })} disabled={busy} title="Clear the form" aria-label="Clear the form">
          <Icon name="reset" />
        </button>
      </div>
    </form>
  );
}
