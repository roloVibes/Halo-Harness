// The designed workflow graph (workflow.json), laid out in code as SVG:
// goal -> lead -> split -> one node per worker lane (stacked) -> merge ->
// test -> gate (a diamond) -> done, and the gate's return arrow back to the
// workers. Pending steps are faint, the running step flows (working), a lit
// diamond is a gate that acted, red is failed.
import { useId } from "react";
import type { MotionState } from "../../lib/motion";
import { Metric, NoRun } from "./bits";
import { laneColor, laneMotion, NONE, setOpt, useOrch } from "./store";
import type { Step, StepState } from "./types";

const COL: Record<string, number> = { goal: 46, lead: 132, split: 218, worker: 340, merge: 466, test: 552, gate: 636, done: 724 };
const NODE_W = 74;
const W = 776;

function stepMotion(state: StepState): MotionState {
  return state === "running" ? "working" : state === "failed" ? "error" : state === "done" ? "done" : "none";
}

function Node({ s, x, y, label }: { s: Step; x: number; y: number; label: string }) {
  return (
    <g className="og-node" data-state={s.state} data-motion={stepMotion(s.state)} transform={`translate(${x - NODE_W / 2} ${y - 15})`}>
      <title>{`${s.label || s.id}: ${s.state}`}</title>
      <rect className="og-shape" width={NODE_W} height={30} rx={8} />
      <text className="og-label" x={NODE_W / 2} y={19} textAnchor="middle">
        {label}
      </text>
    </g>
  );
}

export function Graph({ compact }: { compact?: boolean }) {
  const wf = useOrch((s) => s.data?.workflow);
  const lanes = useOrch((s) => s.data?.lanes);
  const labels = useOrch((s) => s.opts.graphLabels);
  const marker = useId().replace(/:/g, "");
  if (!wf) return <NoRun what="The workflow graph" />;
  const steps = wf.steps;
  const by = (id: string) => steps.find((s) => s.id === id)!;
  const workers = steps.filter((s) => s.kind === "worker");
  const n = Math.max(1, workers.length);
  const rowH = n <= 6 ? 36 : Math.max(7, Math.min(36, 300 / n));
  const top = 16;
  const span = n * rowH;
  const mid = top + span / 2;
  const H = Math.max(compact ? 120 : 150, top + span + 44);
  const loopY = top + span + 26;
  const returned = (lanes || []).some((l) => l.pieces_returned > 0);
  const flow = ["goal", "lead", "split"].map((id) => by(id)).filter(Boolean);
  const tail = ["merge", "test"].map((id) => by(id)).filter(Boolean);
  const gate = by("gate");
  const done = by("done");
  const lit = (id: string) => (by(id)?.state === "done" ? "true" : undefined);
  const wx = COL.worker;
  const gateMotion = stepMotion(gate?.state || "pending");
  return (
    <svg className="og-graph" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Workflow graph" data-testid="orchestra-graph">
      <defs>
        <marker id={marker} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L8 4 L0 8 z" className="og-arrow" />
        </marker>
      </defs>
      {flow.slice(0, -1).map((s, i) => (
        <line key={s.id} className="og-edge" data-lit={lit(s.id)} x1={COL[s.kind] + NODE_W / 2} y1={mid} x2={COL[flow[i + 1].kind] - NODE_W / 2} y2={mid} markerEnd={`url(#${marker})`} />
      ))}
      {workers.map((w, i) => {
        const y = top + i * rowH + rowH / 2;
        const sx = COL.split + NODE_W / 2;
        const ex = COL.merge - NODE_W / 2;
        return (
          <g key={w.id} className="og-fan" data-state={w.state}>
            <path className="og-edge" data-lit={lit("split")} d={`M${sx} ${mid} C${sx + 40} ${mid} ${wx - 95} ${y} ${wx - 56} ${y}`} />
            <path className="og-edge" data-lit={w.state === "done" ? "true" : undefined} d={`M${wx + 56} ${y} C${wx + 95} ${y} ${ex - 40} ${mid} ${ex} ${mid}`} />
          </g>
        );
      })}
      {workers.map((w, i) => {
        const lane = lanes?.find((l) => l.lane === w.lane);
        const h = Math.max(4, rowH - 5);
        const y = top + i * rowH + (rowH - h) / 2;
        const motion = lane ? laneMotion(lane.state) : stepMotion(w.state);
        return (
          <g key={w.id} className="og-node og-worker" data-state={w.state} data-lc={laneColor(w.lane)} data-motion={motion} transform={`translate(${wx - 56} ${y})`}>
            <title>{`lane ${w.lane}: ${lane?.state || w.state}${lane?.title ? ` · ${lane.title}` : ""}`}</title>
            <rect className="og-shape" width={112} height={h} rx={Math.min(8, h / 2)} />
            {labels && rowH >= 16 && (
              <text className="og-label" x={56} y={h / 2 + 4} textAnchor="middle">
                {`lane ${w.lane}${lane?.state ? " · " + lane.state.replace("_", " ") : ""}`}
              </text>
            )}
          </g>
        );
      })}
      {[...tail, gate].slice(0, -1).map((s, i, arr) => {
        const next = i + 1 < arr.length ? arr[i + 1] : gate;
        const x2 = next.kind === "gate" ? COL.gate - 20 : COL[next.kind] - NODE_W / 2;
        return <line key={s.id} className="og-edge" data-lit={lit(s.id)} x1={COL[s.kind] + NODE_W / 2} y1={mid} x2={x2} y2={mid} markerEnd={`url(#${marker})`} />;
      })}
      {gate && done && <line className="og-edge" data-lit={lit("gate")} x1={COL.gate + 20} y1={mid} x2={COL.done - NODE_W / 2} y2={mid} markerEnd={`url(#${marker})`} />}
      <path className="og-loop" data-active={returned || undefined} d={`M${COL.gate} ${mid + 20} V${loopY} H${wx} V${top + span + 2}`} markerEnd={`url(#${marker})`}>
        <title>The gate sends a failed piece back to its worker (up to the return cap)</title>
      </path>
      <text className="og-loop-label" x={(COL.gate + wx) / 2} y={loopY - 5} textAnchor="middle">
        {returned ? "sent back" : "return"}
      </text>
      {[...flow, ...tail].map((s) => (
        <Node key={s.id} s={s} x={COL[s.kind]} y={mid} label={s.kind} />
      ))}
      {gate && (
        <g className="og-node og-gate" data-state={gate.state} data-motion={gateMotion} data-lit={gate.state === "done" || gate.state === "running" || undefined} transform={`translate(${COL.gate} ${mid})`} data-testid="gate">
          <title>{`quality gate: ${gate.state}`}</title>
          <path className="og-shape" d="M0 -20 L20 0 L0 20 L-20 0 Z" />
          <text className="og-label" y={4} textAnchor="middle">
            gate
          </text>
        </g>
      )}
      {done && <Node s={done} x={COL.done} y={mid} label="done" />}
    </svg>
  );
}

export function GraphGlance() {
  const steps = useOrch((s) => s.data?.workflow?.steps);
  const running = steps?.filter((s) => s.state === "running").map((s) => s.id) || [];
  const finished = steps?.filter((s) => s.state === "done" || s.state === "skipped").length || 0;
  return (
    <div className="glance og-graph-glance">
      {steps && (
        <div className="glance-numbers">
          <Metric value={`${finished}/${steps.length}`} label="steps finished" />
          <Metric value={running.length ? running.slice(0, 2).join(", ") : steps.some((s) => s.state === "failed") ? "failed" : "-"} label="running now" tone="accent" />
        </div>
      )}
      <Graph compact />
    </div>
  );
}

export function GraphDetail() {
  const steps = useOrch((s) => s.data?.workflow?.steps || NONE);
  return (
    <div className="og-graph-detail">
      <Graph />
      <ol className="og-steps mono">
        {steps
          .filter((s) => s.kind !== "worker")
          .map((s) => (
            <li key={s.id} data-state={s.state}>
              <span className="og-step-dot" data-motion={stepMotion(s.state)} />
              {s.id} <span className="muted">{s.label}</span> <span className="og-step-state">{s.state}</span>
            </li>
          ))}
      </ol>
    </div>
  );
}

export function GraphSettings() {
  const labels = useOrch((s) => s.opts.graphLabels);
  return (
    <label className="check">
      <input type="checkbox" checked={labels} onChange={(e) => setOpt("graphLabels", e.target.checked)} /> Label the worker lanes
    </label>
  );
}

export function useGraphMotion(): MotionState {
  const steps = useOrch((s) => s.data?.workflow?.steps);
  if (!steps) return "none";
  if (steps.some((s) => s.state === "failed")) return "error";
  return steps.some((s) => s.state === "running") ? "working" : "idle";
}
