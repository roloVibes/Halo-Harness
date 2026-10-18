// The Flow section before a run is open: one centered Start view instead of
// eight empty panels -- the intake form, what a flow does in six numbered
// steps, whether ComfyUI answers (the render step needs it), and the past
// runs to open. FlowView decides between it and the panel workspace (which
// comes up once a run is started or opened, or "open the workspace anyway").
// When ComfyUI does not answer, the Media strips shrink to the status card.
import { useEffect, useMemo } from "react";
import { Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { attachMedia, useMedia } from "../media/store";
import { clock, cost } from "../orchestra/format";
import { FlowGraphView } from "./FlowGraph";
import { IntakeForm } from "./IntakeForm";
import { NONE, runMotion, setView, showsStart, useFlow } from "./store";
import { openRun, startFlow } from "./sync";

const STEPS: [string, string, string][] = [
  ["Brief", "intake", "You write what you want; files you drop become assets of the project."],
  ["Roles", "roles", "A planner and a researcher turn the brief into a plan."],
  ["Marketing org", "org", "A strategist, a copywriter and an art director write the campaign and the image prompt."],
  ["Render you confirm", "render + confirm", "ComfyUI renders the prompt; the run waits until you confirm, redo or stop."],
  ["Post", "post", "One post per platform through Postiz (a dry run unless the flow says live: true)."],
  ["Measure", "metrics", "Views, likes, comments and shares of the live posts, sampled over the next days."],
];

function Comfy() {
  const st = useMedia((s) => s.status);
  const ok = st?.reachable;
  return (
    <div className="fl-start-comfy mono" data-ok={ok === undefined || ok === null ? undefined : String(ok)}>
      <span className="feed-dot" data-status={ok ? "open" : ok === false ? "down" : "connecting"} />
      {ok ? `ComfyUI answers (${st?.version || "?"}): the render step is ready.` : ok === false ? "ComfyUI does not answer: run halo media init --url <its address> before the render step." : "Asking ComfyUI..."}
    </div>
  );
}

function PastRuns() {
  const runs = useFlow((s) => s.runs || NONE);
  return (
    <section className="fl-start-runs" aria-label="Past runs">
      <div className="rail-label mono">PAST RUNS · {runs.length}</div>
      {runs.slice(0, 8).map((r) => {
        const state = r.waiting_step ? "waiting" : r.status;
        return (
          <button key={r.run} className="og-run" onClick={() => void openRun(r.run)}>
            <span className="og-run-dot" data-state={state} data-motion={runMotion(state, !!r.waiting_step, 0)} />
            <span className="mono og-run-id">{r.run}</span>
            <span className="og-run-what">{r.waiting_step ? `waits on you at ${r.waiting_step}` : r.status}</span>
            <span className="mono muted">{r.name} · {cost(r.cost_usd)} · {clock(r.created)}</span>
          </button>
        );
      })}
      {!runs.length && <p className="muted">Your first run shows up here; open any run to see its panels.</p>}
    </section>
  );
}

export function StartView() {
  return (
    <div className="fl-start" data-testid="flow-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">FLOW · YOUR FULL WORKFLOW</div>
          <h1 className="fl-start-title">Start a flow</h1>
          <p className="muted">Write a brief and press Run: Halo takes it through your roles and a marketing org, renders the picture on ComfyUI, waits for your OK, then posts it and measures how it does.</p>
        </header>
        <div className="fl-start-grid">
          <Surface className="fl-start-form" motion="idle">
            <IntakeForm />
          </Surface>
          <aside className="fl-start-side">
            <ol className="fl-explain">
              {STEPS.map(([title, kind, text], i) => (
                <li key={title}>
                  <span className="fl-explain-n mono" data-gate={kind.includes("confirm") || undefined}>{i + 1}</span>
                  <span>
                    <b>{title}</b> <span className="og-chip mono">{kind}</span>
                    <span className="fl-explain-text">{text}</span>
                  </span>
                </li>
              ))}
            </ol>
            <Comfy />
            <PastRuns />
            <button className="og-link mono" onClick={() => setView("workspace")} data-testid="flow-open-workspace">
              open the workspace anyway
            </button>
          </aside>
        </div>
      </div>
    </div>
  );
}

const MEDIA_MORE = ["media-models", "media-workflows", "media-render"];

/** The Flow section: the Start view until a run is open, then the panels. */
export function FlowView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startFlow(), []);
  useEffect(() => attachMedia(), []);
  const start = useFlow(showsStart);
  const graph = useFlow((s) => s.graph);
  const down = useMedia((s) => s.status?.reachable === false);
  const shown = useMemo(() => (down ? specs.filter((p) => !MEDIA_MORE.includes(p.id)) : specs), [down, specs]);
  if (graph) return <FlowGraphView name={graph} />; // 3.0.9.0 R2: "Show as graph"
  if (start) return <StartView />;
  return <Workspace section={section} specs={shown} />;
}
