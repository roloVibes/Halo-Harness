// flow-step: the selected step (click a node in the graph; by default the
// one waiting on you, else the running one, else the last done): cost,
// elapsed, rounds, error, and its output -- per role for a roles step, per
// position for the org (the Art Director's prompt marked), the render's
// prompt and settings. The org's live positions come from the run session's
// subagent frames. A gate open at this step is answered here.
import type { MotionState } from "../../lib/motion";
import { cost, elapsed, short } from "../orchestra/format";
import { Metric, NoFlow, YouChip } from "./bits";
import { GateCard } from "./Gate";
import { currentStep, NONE, selectStep, stepMotion, useFlow } from "./store";
import type { StepRecord } from "./types";

type Out = Record<string, unknown>;

function Block({ title, text, mark }: { title: string; text: string; mark?: string }) {
  return (
    <section className="fl-block" data-mark={mark}>
      <div className="og-goal-label mono">{title}</div>
      <pre className="fl-pre">{text}</pre>
    </section>
  );
}

function asText(v: unknown): string {
  if (v === null || v === undefined) return "";
  return typeof v === "string" ? v : JSON.stringify(v, null, 1);
}

function Positions({ out }: { out: Out }) {
  const live = useFlow((s) => s.positions);
  const pos = (out.positions || {}) as Record<string, { text?: string; prompt?: string }>;
  const names = Array.from(new Set([...Object.keys(pos), ...Object.keys(live)]));
  return (
    <>
      {Object.keys(live).length > 0 && (
        <div className="og-chips" aria-label="Live positions">
          {Object.entries(live).map(([n, st]) => (
            <span key={n} className="og-chip mono fl-live" data-state={st} data-motion={st === "running" ? "working" : st === "failed" ? "error" : "none"}>
              {n} · {st}
            </span>
          ))}
        </div>
      )}
      {names.map((n) =>
        pos[n] ? (
          <div key={n}>
            {pos[n].prompt && <Block title={`${n} · PROMPT`} text={pos[n].prompt!} mark="prompt" />}
            <Block title={n} text={asText(pos[n].text)} />
          </div>
        ) : null,
      )}
    </>
  );
}

function Output({ rec }: { rec: StepRecord }) {
  const out = (rec.output || {}) as Out;
  if (rec.kind === "roles") {
    const per = (out.per_role || {}) as Record<string, string>;
    return <>{Object.entries(per).map(([r, t]) => <Block key={r} title={r} text={t} />)}</>;
  }
  if (rec.kind === "org") return <Positions out={out} />;
  if (rec.kind === "render") {
    const set = (out.set || {}) as Out;
    return (
      <>
        {!!out.prompt && <Block title="PROMPT (from the Art Director)" text={asText(out.prompt)} mark="prompt" />}
        <Block title={`WORKFLOW · ${asText(out.workflow)} · ${asText(out.prompt_id)}`} text={Object.entries(set).map(([k, v]) => `${k} = ${asText(v)}`).join("\n")} />
      </>
    );
  }
  if (!Object.keys(out).length) return null;
  return <Block title={rec.kind === "intake" ? "INTAKE" : "OUTPUT"} text={friendly(out)} />;
}

/** A file path as its last two parts (the project folder says where the rest is). */
function shortPath(v: string): string {
  if (!/^([A-Za-z]:[\\/]|\/)/.test(v)) return v;
  const parts = v.split(/[\\/]/).filter(Boolean);
  return parts.length > 2 ? ".../" + parts.slice(-2).join("/") : v;
}

/** An output as `key: value` lines: paths shortened, lists of files named, nested objects by their keys. */
function friendly(out: Out): string {
  return Object.entries(out)
    .map(([k, v]) => {
      if (typeof v === "string") return `${k}: ${shortPath(v)}`;
      if (Array.isArray(v)) return `${k}: ${v.length ? v.map((x) => (typeof x === "string" ? shortPath(x) : "{...}")).join(", ") : "-"}`;
      if (v && typeof v === "object") return `${k}: ${Object.keys(v).join(", ") || "-"}`;
      return `${k}: ${String(v)}`;
    })
    .join("\n");
}

function useRecord(): StepRecord | undefined {
  const id = useFlow(currentStep);
  return useFlow((s) => s.data?.steps.find((r) => r.id === id));
}

function useStepState(): string | undefined {
  const id = useFlow(currentStep);
  return useFlow((s) => s.data?.flow.steps.find((x) => x.id === id)?.state);
}

function Numbers({ rec }: { rec: StepRecord }) {
  const took = rec.started && rec.finished ? rec.finished - rec.started : rec.started ? Date.now() / 1000 - rec.started : 0;
  return (
    <div className="glance-numbers">
      <Metric value={cost(rec.cost_usd)} label="cost" />
      <Metric value={rec.started ? elapsed(took) : "-"} label="elapsed" />
      <Metric value={rec.rounds ?? 0} label="rounds" />
    </div>
  );
}

function Head() {
  const id = useFlow(currentStep);
  const state = useStepState();
  const kind = useFlow((s) => s.data?.flow.steps.find((x) => x.id === id)?.kind);
  const n = useFlow((s) => (s.data?.flow.steps.findIndex((x) => x.id === id) ?? -1) + 1);
  return (
    <div className="glance-row fl-step-head">
      <span className="og-step-dot" data-motion={stepMotion(state)} />
      <span className="glance-kicker mono">{n} · {(id || "-").toUpperCase()}</span>
      <span className="mono muted">{kind}</span>
      <span className="spacer" />
      <span className="og-badge mono" data-state={state === "done" ? "finished" : state === "failed" ? "stopped" : state}>{(state || "-").toUpperCase()}</span>
    </div>
  );
}

/** A gate open at this step: an org position's card here; the render's confirm gate lives in Renders. */
function GateHere() {
  const id = useFlow(currentStep);
  const gate = useFlow((s) => (s.data?.gate && s.data.gate.step === id ? s.data.gate : null));
  const confirm = useFlow((s) => s.data?.flow.steps.find((x) => x.id === id)?.kind === "confirm");
  if (!gate) return null;
  if (confirm || gate.artboards?.length) return <YouChip />;
  return <GateCard gate={gate} />;
}

export function StepGlance() {
  const rec = useRecord();
  const has = useFlow((s) => !!s.data);
  if (!has) return <NoFlow what="The step detail" />;
  const out = (rec?.output || {}) as Out;
  return (
    <div className="glance fl-step-glance">
      <Head />
      {rec ? <Numbers rec={rec} /> : <div className="og-wait muted">This step runs after the ones before it.</div>}
      {rec?.error && <div className="md-error mono">{rec.error}</div>}
      {rec && <div className="glance-hint">{short(asText(out.prompt || out.text || ""), 140)}</div>}
      <GateHere />
    </div>
  );
}

export function StepDetail() {
  const rec = useRecord();
  const has = useFlow((s) => !!s.data);
  if (!has) return <NoFlow what="The step detail" />;
  return (
    <div className="fl-step">
      <Head />
      <GateHere />
      {rec ? <Numbers rec={rec} /> : <div className="og-wait muted">This step runs after the ones before it: click a done step in Workflow to see its work.</div>}
      {rec?.error && <div className="md-error mono">{rec.error}</div>}
      {rec && <Output rec={rec} />}
    </div>
  );
}

export function StepSettings() {
  const steps = useFlow((s) => s.data?.flow.steps || NONE);
  const id = useFlow(currentStep);
  return (
    <label className="field">
      <span className="field-label mono">SHOW STEP</span>
      <select className="input mono" value={id} onChange={(e) => selectStep(e.target.value)}>
        {steps.map((s) => (
          <option key={s.id} value={s.id}>
            {s.id} · {s.state}
          </option>
        ))}
      </select>
    </label>
  );
}

export function useStepMotion(): MotionState {
  const state = useStepState();
  return state ? stepMotion(state) : "none";
}
