// flow-intake: Glance = the flow's name and its intake summarised (the brief,
// the platforms as chips, the budget, the project) with the run state, the
// cost against the budget and step N of M (what a strip keeps); the full
// face = the open run in one line over the intake form (IntakeForm.tsx);
// Settings = the defaults a new form starts from.
import type { ReactNode } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Field } from "../../lib/ui";
import { cost, short } from "../orchestra/format";
import { CostBar, FlowBadge, Metric } from "./bits";
import { IntakeForm } from "./IntakeForm";
import { flow, platformChoices, platformsOf, runMotion, runState, setOpt, setView, stepCount, useFlow } from "./store";

function Chips({ list }: { list: string[] }) {
  return (
    <span className="og-chips">
      {list.length ? list.map((p) => <span key={p} className="og-chip mono fl-platform" data-platform={p}>{p}</span>) : <span className="muted">-</span>}
    </span>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="og-goal-field">
      <span className="og-goal-label mono">{label}</span>
      <span className="og-goal-text">{children}</span>
    </div>
  );
}

export function IntakeGlance() {
  const data = useFlow((s) => s.data);
  const templates = useFlow((s) => s.templates.length);
  const nm = useFlow(stepCount);
  if (!data)
    return (
      <div className="glance">
        <div className="glance-kicker mono">NEW FLOW</div>
        <div className="glance-text">A brief goes through the roles, the marketing org, a ComfyUI render you confirm, then the posts and their metrics.</div>
        <Button variant="primary" onClick={() => setView("start")}>
          Write a brief
        </Button>
        <div className="glance-hint mono">{templates} flow{templates === 1 ? "" : "s"} to start from</div>
      </div>
    );
  const intake = data.flow.intake || {};
  return (
    <div className="glance fl-intake">
      <div className="glance-row">
        <FlowBadge testid="flow-state" />
        <span className="mono fl-name" title={`run ${data.flow.run}`}>{data.flow.name}</span>
      </div>
      <div className="glance-numbers">
        <Metric value={nm} label="steps done" />
        <Metric value={cost(data.flow.cost_usd)} label={data.flow.budget_usd ? `of ${cost(data.flow.budget_usd)} budget` : "cost so far"} tone="accent" />
      </div>
      <CostBar spent={data.flow.cost_usd} budget={data.flow.budget_usd} bare />
      <div className="og-goal-card">
        <Row label="BRIEF">{short(String(intake.brief || ""), 110) || "-"}</Row>
        <div className="fl-intake-pair">
          <Row label="PLATFORMS">
            <Chips list={platformsOf(intake.platforms)} />
          </Row>
          <Row label="PROJECT">
            <span className="mono">{data.project?.slug || String(intake.project || "-")}</span>
          </Row>
        </div>
      </div>
    </div>
  );
}

export function IntakeDetail() {
  return <IntakeForm runLine />;
}

export function IntakeSettings() {
  const d = useFlow((s) => s.opts.defaults);
  const templates = useFlow((s) => s.templates);
  const t = templates.find((x) => x.name === d.template);
  const put = (patch: Partial<typeof d>) => setOpt("defaults", { ...flow.get().opts.defaults, ...patch });
  return (
    <div className="og-settings">
      <Field label="DEFAULT FLOW">
        {(id) => (
          <select id={id} className="input mono" value={d.template} onChange={(e) => put({ template: e.target.value })}>
            {templates.map((x) => <option key={x.source + x.name} value={x.name}>{x.name}</option>)}
            {!t && <option value={d.template}>{d.template}</option>}
          </select>
        )}
      </Field>
      <Field label="DEFAULT PLATFORMS">
        {() => (
          <span className="og-chips">
            {platformChoices(t).map((p) => (
              <button key={p} className="og-chip mono" aria-pressed={d.platforms.includes(p)} onClick={() => put({ platforms: d.platforms.includes(p) ? d.platforms.filter((x) => x !== p) : [...d.platforms, p] })}>
                {p}
              </button>
            ))}
          </span>
        )}
      </Field>
      <Field label="DEFAULT BUDGET (USD)">
        {(id) => <input id={id} className="input mono" value={d.budget} placeholder="the flow's" onChange={(e) => put({ budget: e.target.value })} />}
      </Field>
      <Field label="DEFAULT PROJECT">
        {(id) => <input id={id} className="input mono" value={d.project} placeholder="none: a new slug per run" onChange={(e) => put({ project: e.target.value })} />}
      </Field>
      <p className="muted">Kept in this browser (halo.studio.flow.opts).</p>
    </div>
  );
}

export function useIntakeMotion(): MotionState {
  const state = useFlow(runState);
  const waiting = useFlow((s) => !!s.data?.gate);
  const doneAt = useFlow((s) => s.doneAt);
  return runMotion(state, waiting, doneAt);
}
