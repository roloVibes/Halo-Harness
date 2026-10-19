// Media render: pick a workflow, set its inputs (the named ones first, every
// node input under a disclosure), the design project and the artboard, then
// Render (POST media/render -> 202). The `media_render` frames carry the
// progress; the result lands as an artboard and shows here inline.
import { useEffect, useState } from "react";
import { settle, type MotionState } from "../../lib/motion";
import { Button, Field } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { design } from "../design/store";
import { media, openInputs, render, useMedia, type InputNode, type RenderArt, type RenderState, type Workflow } from "./store";

type Named = { key: string; value: unknown };

/** The workflow's named inputs (`keys` aliases), once each, with the current value. */
function namedInputs(nodes: InputNode[]): Named[] {
  const out: Named[] = [];
  for (const n of nodes) {
    for (const [alias, input] of Object.entries(n.keys || {})) {
      if (!out.some((x) => x.key === alias)) out.push({ key: alias, value: n.inputs[input] });
    }
  }
  return out;
}

function coerce(text: string, old: unknown): unknown {
  if (typeof old === "number" && /^-?\d+(\.\d+)?$/.test(text.trim())) return Number(text);
  if (typeof old === "boolean") return text === "true";
  return text;
}

export function Thumb({ a }: { a: RenderArt }) {
  if (!a.url) return null;
  return a.kind === "video" ? (
    <video className="md-thumb" src={a.url} controls muted preload="metadata" aria-label={`${a.id} v${a.version ?? ""}`} />
  ) : (
    <img className="md-thumb" src={a.url} alt={`${a.id} v${a.version ?? ""}`} />
  );
}

function Progress({ r }: { r: RenderState | undefined }) {
  if (!r) return null;
  return (
    <div className="md-progress" data-state={r.state}>
      <span className="og-badge mono" data-state={r.state === "done" ? "finished" : r.state === "error" ? "stopped" : "running"}>
        {r.state.toUpperCase()}
      </span>
      <span className="mono md-progress-text">{r.error || r.text || r.prompt_id}</span>
      {r.state === "done" && <div className="md-thumbs">{(r.artboards || []).map((a) => <Thumb key={a.id} a={a} />)}</div>}
    </div>
  );
}

export function RenderDetail() {
  const wfs = useMedia((s) => s.workflows);
  const of = useMedia((s) => s.inputsOf);
  const nodes = useMedia((s) => s.inputs);
  const current = useMedia((s) => s.renders[s.current]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [project, setProject] = useState(() => design.get().slug || "");
  const [artboard, setArtboard] = useState("render");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => setValues({}), [of]);
  useEffect(() => {
    if (!media.get().inputsOf && wfs.length) void openInputs(wfs[0]);
  }, [wfs]);
  const named = namedInputs(nodes);
  const all = nodes.flatMap((n) => Object.entries(n.inputs).map(([k, v]) => ({ key: `${n.node}.${k}`, value: v, label: `${n.node}.${k} (${n.title || n.class_type})` })));
  const field = (key: string, value: unknown, label = key) => (
    <Field key={key} label={label.toUpperCase()}>
      {(id) =>
        String(value ?? "").length > 60 || key === "prompt" || key === "negative" ? (
          <textarea id={id} className="input og-text" rows={2} value={values[key] ?? String(value ?? "")} onChange={(e) => setValues({ ...values, [key]: e.target.value })} />
        ) : (
          <input id={id} className="input mono" value={values[key] ?? String(value ?? "")} onChange={(e) => setValues({ ...values, [key]: e.target.value })} />
        )
      }
    </Field>
  );
  const go = async () => {
    if (!of) return;
    const set: Record<string, unknown> = {};
    const known = new Map<string, unknown>([...named, ...all].map((x) => [x.key, x.value]));
    for (const [k, v] of Object.entries(values)) if (v !== String(known.get(k) ?? "")) set[k] = coerce(v, known.get(k));
    setBusy(true);
    setProblems(await render(of, set, project.trim(), artboard.trim() || "render"));
    setBusy(false);
  };
  const pick = (v: string) => {
    const w = wfs.find((x) => `${x.source}:${x.name}` === v);
    if (w) void openInputs(w as Workflow);
  };
  return (
    <form className="og-form md-render" onSubmit={(e) => (e.preventDefault(), void go())}>
      <Field label="WORKFLOW">
        {(id) => (
          <select id={id} className="input mono" value={of ? `${of.source}:${of.name}` : ""} onChange={(e) => pick(e.target.value)}>
            {!of && <option value="">pick a workflow</option>}
            {wfs.map((w) => (
              <option key={w.source + w.name} value={`${w.source}:${w.name}`}>
                {w.name} ({w.source})
              </option>
            ))}
          </select>
        )}
      </Field>
      {named.map((n) => field(n.key, n.value))}
      {all.length > 0 && (
        <details className="md-support">
          <summary className="mono">every node input · {all.length}</summary>
          <div className="md-all">{all.map((x) => field(x.key, x.value, x.label))}</div>
        </details>
      )}
      <div className="og-form-row">
        <Field label="DESIGN PROJECT" hint="a project slug from Design">
          {(id) => <input id={id} className="input mono" value={project} onChange={(e) => setProject(e.target.value)} />}
        </Field>
        <Field label="ARTBOARD">
          {(id) => <input id={id} className="input mono" value={artboard} onChange={(e) => setArtboard(e.target.value)} />}
        </Field>
      </div>
      {problems.length > 0 && (
        <ul className="og-problems" role="alert">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}
      <div className="og-actions">
        <Button variant="primary" type="submit" disabled={busy || !of || !project.trim()} title={project.trim() ? "Queue the render on ComfyUI" : "Name the design project first"}>
          Render
        </Button>
      </div>
      <Progress r={current} />
    </form>
  );
}

export function RenderGlance() {
  const r = useMedia((s) => s.renders[s.current]);
  const n = useMedia((s) => Object.keys(s.renders).length);
  if (!r)
    return (
      <div className="glance">
        <div className="glance-kicker mono">RENDER</div>
        <div className="glance-text">Queue a ComfyUI workflow into a design project.</div>
        <div className="glance-hint">Expand to pick the workflow and its inputs.</div>
      </div>
    );
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={r.state} label={r.workflow || "render"} tone={r.state === "done" ? "ok" : r.state === "error" ? "bad" : "accent"} />
        <Metric value={n} label="renders here" />
      </div>
      <Progress r={r} />
    </div>
  );
}

export function useRenderMotion(): MotionState {
  const r = useMedia((s) => s.renders[s.current]);
  if (!r) return "none";
  if (r.state === "queued" || r.state === "progress") return "working";
  if (r.state === "error") return "error";
  return settle(r.at, 1600);
}
