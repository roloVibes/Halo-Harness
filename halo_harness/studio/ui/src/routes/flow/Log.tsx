// flow-log: the run's events.jsonl with each line's elapsed time (or the
// clock), a step filter, kind filters and follow; new lines slide in. A
// step tag selects that step in the Step panel.
import { useEffect, useRef } from "react";
import { useRecent, type MotionState } from "../../lib/motion";
import { when } from "../orchestra/format";
import { Metric, NoFlow } from "./bits";
import { NONE, selectStep, setOpt, useFlow } from "./store";
import type { FlowEvent } from "./types";

const KINDS = ["state", "step", "gate", "post", "metric", "report", "note"];

function visible(events: FlowEvent[], step: string, kinds: string[]): FlowEvent[] {
  return events.filter((e) => (!step || e.step === step) && (!kinds.length || kinds.includes(e.kind)));
}

function Filters() {
  const opts = useFlow((s) => s.opts);
  const steps = useFlow((s) => s.data?.flow.steps || NONE);
  const toggle = (k: string) => setOpt("logKinds", opts.logKinds.includes(k) ? opts.logKinds.filter((x) => x !== k) : [...opts.logKinds, k]);
  return (
    <div className="og-log-filters">
      <select className="input mono og-log-lane" value={opts.logStep} onChange={(e) => setOpt("logStep", e.target.value)} aria-label="Step">
        <option value="">every step</option>
        {steps.map((s) => (
          <option key={s.id} value={s.id}>
            {s.id}
          </option>
        ))}
      </select>
      <span className="og-chips" role="group" aria-label="Kinds">
        {KINDS.map((k) => (
          <button key={k} className="og-chip mono" data-kind={k} aria-pressed={opts.logKinds.includes(k)} onClick={() => toggle(k)}>
            {k}
          </button>
        ))}
      </span>
      <label className="check og-follow">
        <input type="checkbox" checked={opts.follow} onChange={(e) => setOpt("follow", e.target.checked)} /> follow
      </label>
    </div>
  );
}

function Line({ e, mode }: { e: FlowEvent; mode: "relative" | "absolute" }) {
  return (
    <li className="og-log-row fl-log-row" data-kind={e.kind} title={e.data ? JSON.stringify(e.data) : undefined}>
      <span className="og-log-time">{when(mode, e.elapsed_s, e.ts)}</span>
      <button className="og-log-lane-tag fl-step-tag" disabled={!e.step} onClick={() => e.step && selectStep(e.step)}>
        {e.step || "run"}
      </button>
      <span className="og-log-kind">{e.kind}</span>
      <span className="og-log-text">{e.text}</span>
    </li>
  );
}

export function LogDetail() {
  const has = useFlow((s) => !!s.data);
  const events = useFlow((s) => s.events);
  const opts = useFlow((s) => s.opts);
  const box = useRef<HTMLOListElement>(null);
  const rows = visible(events, opts.logStep, opts.logKinds);
  useEffect(() => {
    if (opts.follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [rows.length, opts.follow]);
  if (!has) return <NoFlow what="The run log" />;
  return (
    <div className="og-log">
      <Filters />
      <ol className="og-log-list mono" ref={box} aria-label="Flow run log">
        {rows.map((e, i) => (
          <Line key={`${e.ts}-${i}`} e={e} mode={opts.elapsed} />
        ))}
        {!rows.length && <li className="muted">{events.length ? "Clear the filters to see every line." : "Lines appear here as the run works."}</li>}
      </ol>
    </div>
  );
}

export function LogGlance() {
  const has = useFlow((s) => !!s.data);
  const events = useFlow((s) => s.events);
  const mode = useFlow((s) => s.opts.elapsed);
  if (!has) return <NoFlow what="The run log" />;
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={events.length} label="lines" />
        <Metric value={events.filter((e) => e.kind === "gate").length} label="gate lines" tone="warn" />
      </div>
      <ol className="og-log-list mono og-log-mini">
        {events.slice(-3).reverse().map((e, i) => (
          <Line key={`${e.ts}-${i}`} e={e} mode={mode} />
        ))}
      </ol>
    </div>
  );
}

export function LogSettings() {
  const mode = useFlow((s) => s.opts.elapsed);
  return (
    <div className="og-settings">
      <Filters />
      <div className="segmented" role="group" aria-label="Times">
        {(["relative", "absolute"] as const).map((m) => (
          <button key={m} className={mode === m ? "on" : ""} aria-pressed={mode === m} onClick={() => setOpt("elapsed", m)}>
            {m === "relative" ? "elapsed (+12.5s)" : "clock (14:02:09)"}
          </button>
        ))}
      </div>
      <p className="muted">Lines are the run's events.jsonl, newest last; the filters apply to the Expand face.</p>
    </div>
  );
}

export function useLogMotion(): MotionState {
  const last = useFlow((s) => s.lastFrame);
  const live = useFlow((s) => !!s.data?.live);
  const has = useFlow((s) => !!s.data);
  const fresh = useRecent(last, 2500);
  if (!has) return "none";
  return fresh || live ? "working" : "idle";
}
