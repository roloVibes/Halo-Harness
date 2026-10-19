// The Media panels (ComfyUI): Status (MediaStatus.tsx), Models (tabs image /
// video / audio / upscale; the supporting files under a disclosure),
// Workflows (starters and saved; click one for its inputs) and Render
// (MediaRender.tsx). `mediaPanels()` is the group Design adds as optional
// panels; every panel opens on its full face.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { Metric } from "../orchestra/bits";
import { RenderDetail, RenderGlance, useRenderMotion } from "./MediaRender";
import { StatusDetail, StatusGlance, StatusSettings, useStatusMotion } from "./MediaStatus";
import { ago, attachMedia, gib, openInputs, setTab, SUPPORTING, TABS, useMedia, type MediaModel, type Workflow } from "./store";

// -- models --------------------------------------------------------------------------
function ModelRow({ m }: { m: MediaModel }) {
  return (
    <li className="md-model" title={m.ref}>
      <span className="md-model-file mono">{m.file}</span>
      <span className="og-chip mono">{m.family || "-"}</span>
      <span className="mono muted">{m.quant && m.quant !== "unknown" ? m.quant : ""}</span>
      <span className="mono md-size">{gib(m.size_bytes)}</span>
      {m.notes && <span className="md-note muted">{m.notes}</span>}
    </li>
  );
}

export function ModelsGlance() {
  const models = useMedia((s) => s.models);
  const age = useMedia((s) => s.status?.cache?.age_s);
  return (
    <div className="glance">
      <div className="glance-numbers md-counts">
        {TABS.map((t) => (
          <Metric key={t.id} value={models.filter((m) => t.kinds.includes(m.kind)).length} label={t.label} />
        ))}
      </div>
      <div className="glance-hint mono">{models.length ? `${models.length} files · scanned ${ago(age)}` : "Press Scan in Media status to list the models."}</div>
    </div>
  );
}

export function ModelsDetail() {
  const models = useMedia((s) => s.models);
  const tab = useMedia((s) => s.tab);
  const kinds = TABS.find((t) => t.id === tab)?.kinds || [];
  const rows = models.filter((m) => kinds.includes(m.kind));
  const families = new Set(rows.map((m) => m.family).filter(Boolean));
  const support = models.filter((m) => SUPPORTING.includes(m.kind) && (families.has(m.family) || !m.family));
  return (
    <div className="md-detail">
      <div className="segmented" role="tablist" aria-label="Model kind">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === tab} className={t.id === tab ? "on" : ""} onClick={() => setTab(t.id)}>
            {t.label} {models.filter((m) => t.kinds.includes(m.kind)).length}
          </button>
        ))}
      </div>
      {rows.length ? <ul className="md-models">{rows.map((m) => <ModelRow key={m.ref} m={m} />)}</ul> : <Empty title={`Press Scan in Media status to list the ${tab} models.`} body="Added weights to ComfyUI's models folder? Scan again." />}
      {support.length > 0 && (
        <details className="md-support">
          <summary className="mono">supporting files · {support.length} (encoders, LoRAs, VAEs)</summary>
          <ul className="md-models">{support.map((m) => <ModelRow key={m.ref} m={m} />)}</ul>
        </details>
      )}
    </div>
  );
}

// -- workflows -----------------------------------------------------------------------
export function WorkflowsGlance() {
  const wfs = useMedia((s) => s.workflows);
  const reachable = useMedia((s) => s.wfReachable);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={wfs.filter((w) => w.source === "starter").length} label="starters" tone="accent" />
        <Metric value={wfs.filter((w) => w.source !== "starter").length} label={reachable === false ? "saved (cached)" : "saved"} />
      </div>
      <div className="glance-hint mono">{wfs.slice(0, 3).map((w) => w.name).join(" · ") || "no workflows yet"}</div>
    </div>
  );
}

function Inputs() {
  const of = useMedia((s) => s.inputsOf);
  const nodes = useMedia((s) => s.inputs);
  const err = useMedia((s) => s.inputsError);
  if (!of) return <p className="muted">Click a workflow to see the inputs a render can set.</p>;
  if (err) return <div className="md-error mono">{err}</div>;
  return (
    <ol className="md-nodes mono" aria-label={`Inputs of ${of.name}`}>
      {nodes.map((n) => (
        <li key={n.node}>
          <span className="md-node-id">{n.node}</span> <b>{n.title || n.class_type}</b> <span className="muted">{n.class_type}</span>
          <div className="md-node-inputs">{Object.entries(n.inputs).map(([k, v]) => `${n.keys && Object.values(n.keys).includes(k) ? "*" : ""}${k}=${String(v).slice(0, 40)}`).join("  ")}</div>
        </li>
      ))}
    </ol>
  );
}

export function WorkflowsDetail() {
  const wfs = useMedia((s) => s.workflows);
  const of = useMedia((s) => s.inputsOf);
  const pick = (w: Workflow) => void openInputs(w);
  return (
    <div className="md-detail">
      {(["starter", "saved"] as const).map((src) => (
        <section key={src} aria-label={src}>
          <div className="rail-label mono">{src === "starter" ? "STARTERS (shipped)" : "SAVED ON THE SERVER"}</div>
          <div className="og-chips">
            {wfs.filter((w) => (src === "starter" ? w.source === "starter" : w.source !== "starter")).map((w) => (
              <button key={w.name + w.source} className="og-chip mono" aria-pressed={of?.name === w.name && of?.source === w.source} onClick={() => pick(w)}>
                {w.name}
              </button>
            ))}
          </div>
        </section>
      ))}
      <Inputs />
    </div>
  );
}

function useWorkflowsMotion(): MotionState {
  const n = useMedia((s) => s.workflows.length);
  return n ? "idle" : "none";
}

/** A Media panel's motion hook that also attaches the store while it is mounted. */
function attached(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => attachMedia(), []);
    return hook();
  };
}

/** The Media group: optional panels at `y` the palette adds (Design). */
export function mediaPanels(y: number): PanelSpec[] {
  const base = { y, w: 6, h: 40, minW: 4, minH: 12, face: "detail" as const, optional: true };
  const at = (id: string) => ({ ...base, ...HELP[id], id, testid: id });
  return [
    { ...at("media-status"), title: "Media status", x: 0, glance: StatusGlance, detail: StatusDetail, settings: StatusSettings, useMotion: attached(useStatusMotion) },
    { ...at("media-models"), title: "Media models", x: 6, glance: ModelsGlance, detail: ModelsDetail, useMotion: attached(() => "none") },
    { ...at("media-workflows"), title: "Workflows", x: 12, glance: WorkflowsGlance, detail: WorkflowsDetail, useMotion: attached(useWorkflowsMotion) },
    { ...at("media-render"), title: "Render", x: 18, glance: RenderGlance, detail: RenderDetail, useMotion: attached(useRenderMotion) },
  ];
}
