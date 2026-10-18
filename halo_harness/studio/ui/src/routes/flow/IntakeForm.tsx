// The intake form (the Start view and flow-intake): the flow and the model,
// the brief, the platforms as chips, the budget and the design project,
// files dropped as assets (the run is made without starting, each file
// uploaded, then resumed), and `set` overrides for the render under a
// disclosure. Run, Run with --yes (every gate accepted) and Dry run (posts
// stay dry) stay in view at the bottom. Laid out to fit its panel unscrolled.
import { useEffect, useState, type DragEvent } from "react";
import { Button, Field, Icon } from "../../lib/ui";
import { cost } from "../orchestra/format";
import { loadModels, startRun, type IntakeForm as Form, type RunMode } from "./actions";
import { FlowBadge } from "./bits";
import { flow, NONE, platformChoices, platformsOf, showGraph, stepCount, useFlow } from "./store";

const EXAMPLE = "e.g. A 20-second teaser for this week's drum cover: moody stage light, warm amber, ends on the channel name.";

function fresh(template?: string): Form {
  const d = flow.get().opts.defaults;
  return { template: template || d.template, brief: "", platforms: [...d.platforms], budget: d.budget, project: d.project, model: "", set: [], files: [] };
}

function Drop({ files, set }: { files: File[]; set: (f: File[]) => void }) {
  const [over, setOver] = useState(false);
  const add = (list: FileList | null) => list && set([...files, ...Array.from(list).filter((f) => !files.some((x) => x.name === f.name))]);
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    add(e.dataTransfer.files);
  };
  return (
    <label className="fl-drop" data-over={over || undefined} onDragOver={(e) => (e.preventDefault(), setOver(true))} onDragLeave={() => setOver(false)} onDrop={onDrop}>
      <input type="file" multiple hidden onChange={(e) => add(e.target.files)} />
      {!files.length && <span className="mono muted">Drop images or clips here (or click) to give the roles material.</span>}
      {files.map((f) => (
        <span key={f.name} className="og-chip mono" onClick={(e) => (e.preventDefault(), set(files.filter((x) => x !== f)))} title="Click to remove">
          {f.name} · {Math.max(1, Math.round(f.size / 1024))} KB ×
        </span>
      ))}
    </label>
  );
}

function Overrides({ rows, set }: { rows: [string, string][]; set: (v: [string, string][]) => void }) {
  const put = (i: number, k: string, v: string) => set(rows.map((r, j) => (j === i ? [k, v] : r)));
  return (
    <details className="md-support fl-set">
      <summary className="mono">render overrides · {rows.filter(([k]) => k).length} (step.key = value, e.g. render.width = 1080)</summary>
      {rows.map(([k, v], i) => (
        <div key={i} className="og-form-row">
          <input className="input mono" value={k} placeholder="render.width" onChange={(e) => put(i, e.target.value, v)} aria-label="Setting" />
          <input className="input mono" value={v} placeholder="1080" onChange={(e) => put(i, k, e.target.value)} aria-label="Value" />
        </div>
      ))}
      <Button size="sm" variant="ghost" onClick={() => set([...rows, ["", ""]])}>
        + override
      </Button>
    </details>
  );
}

/** The open run in one line, with "copy its brief" into the form. */
function RunLine({ copy }: { copy: (f: Partial<Form>) => void }) {
  const data = useFlow((s) => s.data);
  const nm = useFlow(stepCount);
  if (!data) return null;
  const intake = data.flow.intake || {};
  return (
    <div className="fl-runline" title={String(intake.brief || "")}>
      <FlowBadge testid="flow-state" />
      <span className="mono">{nm} steps · {cost(data.flow.cost_usd)}{data.flow.budget_usd ? ` of ${cost(data.flow.budget_usd)}` : ""}</span>
      <button type="button" className="og-link mono" onClick={() => copy({ brief: String(intake.brief || ""), platforms: platformsOf(intake.platforms) })}>
        copy its brief
      </button>
    </div>
  );
}

export function IntakeForm({ runLine }: { runLine?: boolean }) {
  const templates = useFlow((s) => s.templates);
  const models = useFlow((s) => s.models);
  const pick = useFlow((s) => s.pick);
  const live = useFlow((s) => (s.runs || NONE).find((r) => r.live)?.run || "");
  const [form, setForm] = useState<Form>(() => fresh(flow.get().pick));
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => loadModels(), []);
  useEffect(() => {
    if (pick) setForm((f) => ({ ...f, template: pick }));
  }, [pick]);
  const t = templates.find((x) => x.name === form.template);
  const set = <K extends keyof Form>(k: K) => (v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  const toggle = (p: string) => set("platforms")(form.platforms.includes(p) ? form.platforms.filter((x) => x !== p) : [...form.platforms, p]);
  const go = async (mode: RunMode) => {
    setBusy(true);
    setProblems(await startRun(form, mode));
    setBusy(false);
  };
  const groups = Array.from(new Set(models.map((m) => m.provider || m.group || "other")));
  const why = live ? `Run ${live} is live: stop it or wait for its report` : !form.brief.trim() ? "Write the brief first" : "";
  return (
    <form className="og-form fl-form" onSubmit={(e) => (e.preventDefault(), void go("run"))} data-testid="flow-intake-form">
      {runLine && <RunLine copy={(f) => setForm((x) => ({ ...x, ...f }))} />}
      <div className="og-form-row">
        <Field label="FLOW">
          {(id) => (
            <select id={id} className="input mono" value={form.template} onChange={(e) => set("template")(e.target.value)}>
              {!t && <option value={form.template}>{form.template}</option>}
              {templates.map((x) => (
                <option key={x.source + x.name} value={x.name} disabled={!!x.error} title={x.path}>
                  {x.name}{x.source !== "template" ? ` (${x.source})` : ""}{x.error ? " -- does not load" : ""}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="MODEL">
          {(id) => (
            <select id={id} className="input mono" value={form.model} onChange={(e) => set("model")(e.target.value)} title="The model the roles and the org use">
              <option value="">lineup default</option>
              {groups.map((g) => (
                <optgroup key={g} label={g}>
                  {models.filter((m) => (m.provider || m.group || "other") === g).map((m) => (
                    <option key={m.ref} value={m.ref}>{m.ref}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          )}
        </Field>
      </div>
      <button type="button" className="og-link mono fl-graph-link" onClick={() => showGraph(form.template)} data-testid="flow-show-graph"
              title="The flow's steps as cards in their dependency layers; drag independent steps to reorder them">
        Show {form.template} as a graph
      </button>
      <Field label="BRIEF">
        {(id) => <textarea id={id} className="input og-text" rows={runLine ? 2 : 4} placeholder={EXAMPLE} value={form.brief} onChange={(e) => set("brief")(e.target.value)} />}
      </Field>
      <Field label="POST ON">
        {() => (
          <span className="og-chips" role="group" aria-label="Platforms">
            {platformChoices(t).map((p) => (
              <button key={p} type="button" className="og-chip mono" aria-pressed={form.platforms.includes(p)} onClick={() => toggle(p)}>
                {p}
              </button>
            ))}
          </span>
        )}
      </Field>
      <div className="og-form-row">
        <Field label="BUDGET (USD)">
          {(id) => <input id={id} className="input mono" inputMode="decimal" placeholder={t?.budget_usd ? String(t.budget_usd) : "the flow's"} value={form.budget} onChange={(e) => set("budget")(e.target.value)} />}
        </Field>
        <Field label="DESIGN PROJECT">
          {(id) => <input id={id} className="input mono" placeholder="e.g. drum-teaser" value={form.project} onChange={(e) => set("project")(e.target.value)} />}
        </Field>
      </div>
      <Drop files={form.files} set={set("files")} />
      <Overrides rows={form.set} set={set("set")} />
      {problems.length > 0 && (
        <ul className="og-problems" role="alert">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}
      <div className="og-actions fl-actions">
        <Button variant="primary" type="submit" disabled={busy || !!why} title={why || "Start the run: it waits for your OK on the render"}>
          Run
        </Button>
        <Button onClick={() => void go("yes")} disabled={busy || !!why} title={why || "Start the run and accept every gate (--yes)"}>
          Run with --yes
        </Button>
        <Button onClick={() => void go("dry")} disabled={busy || !!why} title={why || "Go through every step; the posts stay dry runs"}>
          Dry run
        </Button>
        <button type="button" className="icon-btn" onClick={() => setForm(fresh(form.template))} disabled={busy} title="Clear the form" aria-label="Clear the form">
          <Icon name="reset" />
        </button>
      </div>
    </form>
  );
}
