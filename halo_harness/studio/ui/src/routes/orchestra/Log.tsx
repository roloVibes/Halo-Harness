// Log: the run's timed log (events.jsonl) with each line's elapsed time,
// a lane filter, kind filters and an auto-follow toggle; new lines slide in.
import { useEffect, useRef } from "react";
import { useRecent, type MotionState } from "../../lib/motion";
import { Metric, NoRun } from "./bits";
import { when } from "./format";
import { focusLane, laneColor, NONE, orch, setOpt, useOrch } from "./store";
import type { RunEvent } from "./types";

const KINDS = ["state", "claim", "merge", "gate", "report", "note"];

function visible(events: RunEvent[], lane: number, kinds: string[]): RunEvent[] {
  return events.filter((e) => (!lane || e.lane === lane) && (!kinds.length || kinds.includes(e.kind)));
}

function Filters() {
  const opts = useOrch((s) => s.opts);
  const lanes = (useOrch((s) => s.data?.lanes) || NONE).map((l) => l.lane);
  const toggle = (k: string) => setOpt("logKinds", opts.logKinds.includes(k) ? opts.logKinds.filter((x) => x !== k) : [...opts.logKinds, k]);
  return (
    <div className="og-log-filters">
      <select className="input mono og-log-lane" value={opts.logLane} onChange={(e) => setOpt("logLane", Number(e.target.value))} aria-label="Lane">
        <option value={0}>every lane</option>
        {lanes.map((n) => (
          <option key={n} value={n}>
            lane {n}
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

export function LogDetail() {
  const has = useOrch((s) => !!s.data);
  const events = useOrch((s) => s.events);
  const opts = useOrch((s) => s.opts);
  const box = useRef<HTMLOListElement>(null);
  const rows = visible(events, opts.logLane, opts.logKinds);
  useEffect(() => {
    if (opts.follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [rows.length, opts.follow]);
  if (!has) return <NoRun what="The run log" />;
  return (
    <div className="og-log">
      <Filters />
      <ol className="og-log-list mono" ref={box} aria-label="Run log">
        {rows.map((e, i) => (
          <li key={`${e.ts}-${i}`} className="og-log-row" data-kind={e.kind} title={JSON.stringify(e.data)}>
            <span className="og-log-time">{when(opts.elapsed, e.elapsed_s, e.ts)}</span>
            <button className="og-log-lane-tag" data-lc={laneColor(e.lane)} disabled={!e.lane} onClick={() => e.lane && focusLane(e.lane)}>
              {e.lane ? `lane ${e.lane}` : "run"}
            </button>
            <span className="og-log-kind">{e.kind}</span>
            <span className="og-log-text">{e.text}</span>
          </li>
        ))}
        {!rows.length && <li className="muted">{events.length ? "No line matches the filters." : "No lines yet."}</li>}
      </ol>
    </div>
  );
}

export function LogGlance() {
  const events = useOrch((s) => s.events);
  const mode = useOrch((s) => s.opts.elapsed);
  const has = useOrch((s) => !!s.data);
  if (!has) return <NoRun what="The run log" />;
  const last = events.slice(-3).reverse();
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={events.length} label="lines" />
        <Metric value={events.filter((e) => e.kind === "merge").length} label="merge lines" tone="ok" />
      </div>
      <ol className="og-log-list mono og-log-mini">
        {last.map((e, i) => (
          <li key={`${e.ts}-${i}`} className="og-log-row" data-kind={e.kind}>
            <span className="og-log-time">{when(mode, e.elapsed_s, e.ts)}</span>
            <span className="og-log-text">{e.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function LogSettings() {
  return (
    <div className="og-settings">
      <Filters />
      <p className="muted">Filters apply to the Expand face. Lines are the run's events.jsonl, newest last.</p>
    </div>
  );
}

export function useLogMotion(): MotionState {
  const last = useOrch((s) => s.lastFrame);
  const live = useOrch((s) => !!s.data?.live);
  const fresh = useRecent(last, 2500);
  if (!orch.get().data) return "none";
  return fresh || live ? "working" : "idle";
}
