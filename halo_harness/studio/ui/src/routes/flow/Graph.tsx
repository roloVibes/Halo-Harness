// flow-graph: the run's steps as nodes in order (intake -> plan -> marketing
// -> render -> approve -> publish -> measure -> done), laid out in code as
// SVG. Pending steps are faint, the running one's outline flows (working), a
// `confirm` step is a diamond that lights amber while it waits on you, done
// is green, failed red. The redo arrow runs from the gate back to the render
// it re-runs. Expanded, the org step shows its positions as a sub-row.
import { useId } from "react";
import type { MotionState } from "../../lib/motion";
import { Metric, NoFlow, YouChip } from "./bits";
import { currentStep, NONE, selectStep, stepCount, stepMotion, useFlow } from "./store";
import type { FlowStep } from "./types";

const GAP = 100;
const NODE_W = 84;

function Node({ s, x, y, picked }: { s: FlowStep; x: number; y: number; picked: boolean }) {
  return (
    <g className="og-node fl-node" data-state={s.state} data-motion={stepMotion(s.state)} data-picked={picked || undefined} transform={`translate(${x - NODE_W / 2} ${y - 18})`} onClick={() => selectStep(s.id)} role="button" aria-label={`${s.id}: ${s.state}`}>
      <title>{`${s.id} (${s.kind}): ${s.state}`}</title>
      <rect className="og-shape" width={NODE_W} height={36} rx={9} />
      <text className="og-label fl-label" x={NODE_W / 2} y={16} textAnchor="middle">{s.id}</text>
      <text className="fl-kind" x={NODE_W / 2} y={29} textAnchor="middle">{s.kind}</text>
    </g>
  );
}

function Diamond({ s, x, y, picked }: { s: FlowStep; x: number; y: number; picked: boolean }) {
  const motion: MotionState = s.state === "waiting" ? "waiting" : stepMotion(s.state);
  return (
    <g className="og-node og-gate fl-gate" data-state={s.state} data-motion={motion} data-lit={s.state === "waiting" || s.state === "done" || undefined} data-picked={picked || undefined} transform={`translate(${x} ${y})`} onClick={() => selectStep(s.id)} role="button" aria-label={`${s.id}: the human gate, ${s.state}`} data-testid="gate-diamond">
      <title>{`${s.id}: the human gate (${s.state === "waiting" ? "waiting on you" : s.state})`}</title>
      <path className="og-shape" d="M0 -25 L27 0 L0 25 L-27 0 Z" />
      <text className="og-label" y={4} textAnchor="middle">{s.state === "waiting" ? "you" : s.state === "done" ? "✓" : s.state === "failed" ? "✗" : "gate"}</text>
      <text className="fl-kind" y={-30} textAnchor="middle">{s.id}</text>
    </g>
  );
}

export function FlowGraph({ positions }: { positions?: boolean }) {
  const steps = useFlow((s) => s.data?.flow.steps || NONE);
  const records = useFlow((s) => s.data?.steps || NONE);
  const gate = useFlow((s) => s.data?.gate);
  const live = useFlow((s) => s.positions);
  const picked = useFlow(currentStep);
  const marker = useId().replace(/:/g, "");
  if (!steps.length) return <NoFlow what="The workflow graph" />;
  const W = Math.max(640, steps.length * GAP + 8);
  const x = (i: number) => 4 + GAP / 2 + i * GAP;
  const mid = 42;
  const org = steps.findIndex((s) => s.kind === "org");
  const orgOut = records.find((r) => r.id === steps[org]?.id)?.output as { positions?: Record<string, unknown> } | undefined;
  const names = Array.from(new Set([...Object.keys(orgOut?.positions || {}), ...Object.keys(live)]));
  const showPos = positions && org >= 0 && names.length > 0;
  const confirm = steps.findIndex((s) => s.kind === "confirm");
  const tgtId = gate?.step === steps[confirm]?.id && gate?.target ? gate.target : [...steps.slice(0, Math.max(0, confirm))].reverse().find((s) => s.kind === "render")?.id;
  const target = tgtId ? steps.findIndex((s) => s.id === tgtId) : -1;
  const redoRounds = records.find((r) => r.id === steps[target]?.id)?.rounds || 0;
  const loopY = mid + 38;
  const H = showPos ? loopY + 48 : loopY + 14;
  return (
    <svg className="og-graph fl-graph" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Flow graph">
      <defs>
        <marker id={marker} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L8 4 L0 8 z" className="og-arrow" />
        </marker>
      </defs>
      {steps.slice(0, -1).map((s, i) => {
        const x1 = x(i) + (s.kind === "confirm" ? 27 : NODE_W / 2);
        const x2 = x(i + 1) - (steps[i + 1].kind === "confirm" ? 29 : NODE_W / 2 + 2);
        return <line key={s.id} className="og-edge" data-lit={s.state === "done" || undefined} x1={x1} y1={mid} x2={x2} y2={mid} markerEnd={`url(#${marker})`} />;
      })}
      {confirm >= 0 && target >= 0 && target < confirm && (
        <g>
          <path className="og-loop" data-active={redoRounds > 1 || undefined} d={`M${x(confirm)} ${mid + 25} V${loopY} H${x(target)} V${mid + 20}`} markerEnd={`url(#${marker})`}>
            <title>Redo sends the render back with your instruction</title>
          </path>
          <text className="og-loop-label" x={(x(confirm) + x(target)) / 2} y={loopY - 4} textAnchor="middle">
            {redoRounds > 1 ? `redo · ${redoRounds} renders` : "redo"}
          </text>
        </g>
      )}
      {steps.map((s, i) =>
        s.kind === "confirm" ? <Diamond key={s.id} s={s} x={x(i)} y={mid} picked={picked === s.id} /> : <Node key={s.id} s={s} x={x(i)} y={mid} picked={picked === s.id} />,
      )}
      {showPos &&
        names.map((n, j) => {
          const span = Math.min(W - 8, names.length * 92);
          const left = Math.max(4, Math.min(W - 4 - span, x(org) - span / 2));
          const px = left + j * (span / names.length) + span / names.length / 2;
          const state = live[n] || (steps[org].state === "done" ? "done" : steps[org].state === "running" ? "running" : "pending");
          const motion = state === "running" ? "working" : state === "failed" ? "error" : state === "done" ? "done" : gate?.position === n ? "waiting" : "none";
          return (
            <g key={n} className="og-node fl-pos" data-state={gate?.position === n ? "waiting" : state} data-motion={motion} transform={`translate(${px - 42} ${loopY + 14})`}>
              <title>{`${n}: ${state}`}</title>
              <line className="og-edge" x1={42} y1={-2} x2={x(org) - px + 42} y2={-28} />
              <rect className="og-shape" width={84} height={20} rx={10} />
              <text className="fl-kind fl-pos-label" x={42} y={14} textAnchor="middle">{n.length > 13 ? n.slice(0, 12) + "…" : n}</text>
            </g>
          );
        })}
    </svg>
  );
}

/** The big numbers: steps done, and what runs now (or waits on you, or how the run ended). */
function Numbers() {
  const nm = useFlow(stepCount);
  const steps = useFlow((s) => s.data?.flow.steps);
  const gate = useFlow((s) => s.data?.gate);
  const status = useFlow((s) => s.data?.report?.status);
  if (!steps) return null;
  const running = steps.find((s) => s.state === "running");
  return (
    <div className="glance-row">
      <div className="glance-numbers">
        <Metric value={nm} label="steps done" />
        <Metric
          value={gate ? gate.step : running ? running.id : status || (steps.some((s) => s.state === "failed") ? "failed" : "-")}
          label={gate ? "waiting on you" : running ? "running now" : "the run"}
          tone={gate ? "warn" : status === "finished" ? "ok" : status ? "bad" : "accent"}
        />
      </div>
      <span className="spacer" />
      <YouChip />
    </div>
  );
}

/** The run's last log line: what it is doing now. */
function Now() {
  const last = useFlow((s) => s.events[s.events.length - 1]);
  if (!last) return null;
  return (
    <div className="glance-hint mono fl-now" key={`${last.ts}`} title={last.text}>
      {last.step && <span className="fl-now-step">{last.step} </span>}
      {last.text}
    </div>
  );
}

export function GraphGlance() {
  return (
    <div className="glance og-graph-glance fl-graph-glance">
      <Numbers />
      <FlowGraph />
      <Now />
    </div>
  );
}

export function GraphDetail() {
  return (
    <div className="glance og-graph-glance fl-graph-glance">
      <Numbers />
      <FlowGraph positions />
      <Now />
    </div>
  );
}

export function useGraphMotion(): MotionState {
  const steps = useFlow((s) => s.data?.flow.steps);
  const gate = useFlow((s) => !!s.data?.gate);
  if (!steps) return "none";
  if (gate) return "waiting";
  if (steps.some((s) => s.state === "failed")) return "error";
  return steps.some((s) => s.state === "running") ? "working" : "idle";
}
