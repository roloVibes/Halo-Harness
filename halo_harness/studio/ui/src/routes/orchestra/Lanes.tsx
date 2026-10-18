// Lanes: the timeline. One horizontal trace per worker from "joined" to
// "merged" on the run's clock, a node at each state change (joined, writing,
// written, in review, merged) with its time, a diamond where the gate sent
// the piece back; the running lane's trace flows (working), a waiting lane
// pulses amber. Hover a node for its time and text; click a lane to focus
// it (its node times show). 3.0.9.0: a lane that starts after another is
// joined to it by an arc with a chip naming what it takes, and every lane
// shows its base (LaneEdges.tsx). 3.1.2.0 R2: a lane whose upstream the gate
// sent back shows STALE until it is re-based, then the re-base line.
import { useEffect, useRef } from "react";
import type { MotionState } from "../../lib/motion";
import { Metric, NoRun } from "./bits";
import { elapsed, when } from "./format";
import { counters, focusLane, LANE_LABEL, laneColor, laneMotion, liveNow, setOpt, useOrch } from "./store";
import { BaseLine, EdgeArcs, EdgeChips, laneEdges } from "./LaneEdges";
import type { Lane } from "./types";

function span(lanes: Lane[], created: number, now: number): [number, number] {
  let end = now || created + 1;
  for (const l of lanes) for (const h of l.history) end = Math.max(end, h.ts);
  return [created, Math.max(end, created + 1)];
}

function Trace({ lane, t0, t1, live }: { lane: Lane; t0: number; t1: number; live: boolean }) {
  const mode = useOrch((s) => s.opts.elapsed);
  const pct = (ts: number) => `${(((ts - t0) / (t1 - t0)) * 100).toFixed(2)}%`;
  const first = lane.history[0];
  if (!first) return <div className="og-trace og-trace-empty" />;
  const ended = lane.state === "merged" || lane.state === "failed";
  const last = ended || !live ? lane.history[lane.history.length - 1].ts : t1;
  return (
    <div className="og-trace" data-lc={laneColor(lane.lane)}>
      <span className="og-trace-line" data-motion={laneMotion(lane.state)} style={{ left: pct(first.ts), width: `calc(${pct(last)} - ${pct(first.ts)})` }} />
      {lane.history.map((h, i) => (
        <span
          key={i}
          className={"og-trace-node" + (h.state === "waiting" ? " og-diamond" : "")}
          data-state={h.state}
          style={{ left: pct(h.ts) }}
          title={`${LANE_LABEL[h.state] || h.state} ${when(mode, h.elapsed_s, h.ts)}${h.text ? ": " + h.text : ""}`}
        >
          <span className="og-trace-tag mono">
            {LANE_LABEL[h.state] || h.state} {when(mode, h.elapsed_s, h.ts)}
          </span>
        </span>
      ))}
    </div>
  );
}

export function LanesDetail() {
  const data = useOrch((s) => s.data);
  const focus = useOrch((s) => s.focusLane);
  const mode = useOrch((s) => s.opts.elapsed);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.querySelector(`[data-lane="${focus}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focus]);
  if (!data) return <NoRun what="The lane timeline" />;
  if (!data.lanes.length)
    return <div className="og-wait muted">No lanes yet: the lead is splitting the goal into jobs ({data.goal.workers} worker{data.goal.workers === 1 ? "" : "s"}).</div>;
  const [t0, t1] = span(data.lanes, data.run.created, liveNow(data));
  const edges = laneEdges(data.lanes);
  return (
    <div className="og-lanes" ref={box} data-edges={edges.length || undefined}>
      <EdgeArcs edges={edges} box={box} lanes={data.lanes} />
      <div className="og-axis mono muted">
        <span>{elapsed(0)}</span>
        <span>{elapsed((t1 - t0) / 2)}</span>
        <span>{elapsed(t1 - t0)}</span>
      </div>
      {data.lanes.map((l) => (
        <div
          key={l.lane}
          className="og-lane"
          data-testid="lane"
          data-lane={l.lane}
          data-lc={laneColor(l.lane)}
          data-focus={focus === l.lane || undefined}
          onClick={() => focusLane(focus === l.lane ? null : l.lane)}
        >
          <div className="og-lane-head">
            <span className="og-lane-n mono">{l.lane}</span>
            <span className="og-lane-name">
              <span className="og-lane-title" title={l.claims.join(", ")}>
                {l.title || l.claims.join(", ")}
              </span>
              <EdgeChips lane={l} edges={edges} />
            </span>
          </div>
          <Trace lane={l} t0={t0} t1={t1} live={data.live} />
          <div className="og-lane-state mono" data-state={l.state} data-motion={laneMotion(l.state)}>
            {LANE_LABEL[l.state] || l.state}
            {l.pieces_returned > 0 && <span className="og-returned"> ↺{l.pieces_returned}</span>}
            {l.stale && <span className="og-chip mono og-stale" data-testid="lane-stale" title={l.stale.reason}>STALE</span>}
            {l.rebased && !l.stale && (
              <span className="og-rebase mono" data-testid="lane-rebase" data-conflict={l.rebased.conflict?.length || undefined}
                    title={l.rebased.conflict?.length ? `the re-base conflicted in ${l.rebased.conflict.join(", ")}: its worker resolved it` : "re-based"}>
                re-based onto {l.rebased.onto.map((o) => `lane ${o.lane} ${o.head.slice(0, 7)}`).join(", ")}
              </span>
            )}
            {l.history.length > 0 && <span className="og-lane-when">{when(mode, l.history[l.history.length - 1].elapsed_s, l.history[l.history.length - 1].ts)}</span>}
            <BaseLine lane={l} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function LanesGlance() {
  const lanes = useOrch((s) => s.data?.lanes);
  if (!lanes) return <NoRun what="The lanes" />;
  const c = counters(lanes);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={c.joined} label="joined" />
        <Metric value={c.writing} label="writing" tone="accent" />
        <Metric value={c.merged} label="merged" tone="ok" />
      </div>
      <div className="og-strips" aria-hidden="true">
        {lanes.map((l) => (
          <span key={l.lane} className="og-strip" data-lc={laneColor(l.lane)} data-state={l.state} data-motion={laneMotion(l.state)} />
        ))}
      </div>
      <div className="glance-hint">{c.waiting ? `${c.waiting} lane${c.waiting === 1 ? "" : "s"} waiting on a piece sent back` : "Expand for the timeline"}</div>
    </div>
  );
}

export function LanesSettings() {
  const mode = useOrch((s) => s.opts.elapsed);
  return (
    <div className="segmented" role="group" aria-label="Times">
      {(["relative", "absolute"] as const).map((m) => (
        <button key={m} className={mode === m ? "on" : ""} aria-pressed={mode === m} onClick={() => setOpt("elapsed", m)}>
          {m === "relative" ? "Elapsed (+12.5s)" : "Clock (14:02:09)"}
        </button>
      ))}
    </div>
  );
}

export function useLanesMotion(): MotionState {
  const lanes = useOrch((s) => s.data?.lanes);
  if (!lanes || !lanes.length) return "none";
  if (lanes.some((l) => l.state === "failed")) return "error";
  if (lanes.some((l) => l.state === "waiting")) return "waiting";
  return lanes.some((l) => l.state === "writing" || l.state === "in_review") ? "working" : "idle";
}
