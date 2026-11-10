// The open mission's parts on Live's fleet scope (3.3.16.0 R2 "the Fleet fold"; the Fleet Map's mission layer,
// MapMission.tsx, before): each part a node under the machine it runs on (dashed while planned, solid once it runs; the
// motion colours: amber asked, cyan running, green done, red failed), an edge for each depends_on -- amber with a
// `claims` chip where two parts were put one after the other because their claims overlap, else a chip naming what it
// hands on -- a repo part's base, a red chip on a part nobody can run, a lock on one pinned by capability. Drag a part
// into another machine's box to move it there (the route checks it in code; a 422 snaps it back with the reason in a
// toast). A click picks the part: the inspector shows its card, its row in Runs' plan table lights.
import { useRef, useState, type PointerEvent as PE, type ReactElement } from "react";
import { short } from "../../orchestra/format";
import { EDITABLE, missions, partMotion, partState, useMissions, usd, type PlanPart, type View } from "../../fleet/mstore";
import { reassign } from "../../fleet/mload";
import { partAgent } from "../../fleet/MissionRun";
import { handoffLabel, partBase } from "../../fleet/missionText";
import { useFleet } from "../../fleet/store";
import type { LiveBox, LiveGroup } from "../../roles/liveLayout";
import { pickLive } from "./scope";

type Held = { x: number; y: number; moved: boolean; dx: number; dy: number };

export function PartNode({ b, machines, zoom }: { b: LiveBox; machines: LiveGroup[]; zoom: number }) {
  const v = useMissions((s) => s.view);
  const pid = b.node.id.slice(2);
  const p = v?.plan?.parts.find((x) => x.id === pid);
  const sel = useMissions((s) => s.selPart === pid);
  const held = useMissions((s) => (s.drag?.part === pid ? s.drag : null));
  const harnesses = useFleet((s) => s.harnesses);
  const [off, setOff] = useState<{ dx: number; dy: number } | null>(null);
  const start = useRef<Held | null>(null);
  if (!v || !p) return null;
  const st = partState(v, p.id);
  const editable = EDITABLE.includes(v.mission.state);
  const o = held || off;
  const down = (e: PE<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    start.current = { x: e.clientX, y: e.clientY, moved: false, dx: 0, dy: 0 };
  };
  const move = (e: PE<HTMLDivElement>) => {
    const s0 = start.current;
    if (!s0 || !editable) return;
    const dx = (e.clientX - s0.x) / zoom, dy = (e.clientY - s0.y) / zoom;
    if (!s0.moved && Math.hypot(dx, dy) < 4) return;
    Object.assign(s0, { moved: true, dx, dy });
    setOff({ dx, dy });
  };
  const up = () => {
    const s0 = start.current;
    start.current = null;
    if (!s0?.moved) {
      setOff(null);
      missions.update(() => ({ selPart: p.id }));
      pickLive("part", p.id);
      return;
    }
    const cx = b.x + b.w / 2 + s0.dx, cy = b.y + b.h / 2 + s0.dy;
    const box = machines.find((g) => cx >= g.x && cx <= g.x + g.w && cy >= g.y && cy <= g.y + g.h);
    if (box && box.card !== b.node.harness) {
      missions.update(() => ({ drag: { part: p.id, dx: s0.dx, dy: s0.dy, pending: true } }));
      void reassign(p.id, box.card, harnesses.find((h) => h.id === box.card)?.name || box.label);
    }
    setOff(null);
  };
  const run = v.mission.parts?.[p.id];
  const live = st === "running" ? partAgent(harnesses, v.mission.id, p.id, run?.harness || p.harness) : null;
  const line = st === "asked" ? `waiting on ${run?.harness_name || p.harness_name || "its"} owner`
    : live ? String(live.agent.current || live.agent.last_text || "working") : p.unassignable || p.reason || p.brief;
  const base = partBase(v, p);
  return (
    <div className="rlm-node rlm-part" style={{ left: b.x + (o?.dx || 0), top: b.y + (o?.dy || 0), width: b.w, height: b.h }}
         data-testid="fleet-part" data-part={p.id} data-harness={p.harness || ""} data-state={st} data-motion={partMotion(st)}
         data-pinned={p.pinned || undefined} data-selected={sel || undefined} data-drag={o ? (held ? "pending" : "moving") : undefined}
         data-editable={editable || undefined} onPointerDown={down} onPointerMove={move} onPointerUp={up}
         onPointerCancel={() => ((start.current = null), setOff(null))} role="button" tabIndex={0} aria-label={`part ${p.id}: ${p.title}, ${st}`}
         title={`part ${p.id}: ${p.title}\n${p.harness_name ? "on " + p.harness_name + (p.reason ? ": " + p.reason : "") : "no harness"}${editable ? "\ndrag it to another machine's box to move it" : ""}`}>
      <div className="rlm-head">
        <span className="rlm-dot" aria-hidden="true" />
        <b className="rlm-name mono">{p.id}</b>
        <b className="rlm-name">{short(p.title, 18)}</b>
        <span className="spacer" />
        {p.pinned && <span className="rlm-lock" data-testid="fleet-part-lock" title={`pinned: ${p.reason}`}>lock</span>}
        {p.unassignable && <span className="og-chip mono rlm-bad" data-testid="fleet-part-unassignable" title={p.unassignable}>unassignable</span>}
        <span className="og-chip mono">{p.kind}</span>
      </div>
      <div className="muted rlm-line" title={line}>{short(line, 52)}</div>
      <div className="mono muted rlm-line">
        {base && <span data-testid="part-base">{base}</span>}
        <span className="spacer" />
        {run?.cost_usd ? usd(run.cost_usd) : `est ${usd(p.est_cost_usd)}`}
      </div>
    </div>
  );
}

/** Each depends_on as an edge between part nodes, with its chip (claims, or what it hands on). */
export function PartEdges({ boxes, w, h }: { boxes: LiveBox[]; w: number; h: number }) {
  const v = useMissions((s) => s.view);
  if (!v?.plan) return null;
  const pos = new Map(boxes.filter((b) => b.node.kind === "part").map((b) => [b.node.id.slice(2), b]));
  const out: ReactElement[] = [];
  for (const p of v.plan.parts) out.push(...edgesOf(v, p, pos));
  return (
    <svg className="rlm-edges rlm-part-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} data-testid="fleet-mission-layer" data-mission={v.mission.id}>
      {out}
    </svg>
  );
}

function edgesOf(v: View, p: PlanPart, pos: Map<string, LiveBox>): ReactElement[] {
  const b = pos.get(p.id);
  return p.depends_on.flatMap((d) => {
    const a = pos.get(d);
    if (!a || !b) return [];
    const seq = (p.sequenced || []).find((x) => x.after === d);
    const x1 = a.x + a.w, y1 = a.y + a.h / 2, x2 = b.x + b.w, y2 = b.y + b.h / 2;
    const bend = Math.max(34, Math.abs(y2 - y1) / 3, Math.abs(x2 - x1) / 4);
    const mx = Math.max(x1, x2) + bend * 0.75, my = (y1 + y2) / 2;
    const label = seq ? "claims" : short(handoffLabel(v, p, d), 22);
    const cw = 14 + label.length * 6;
    return [
      <g key={`${d}>${p.id}`} className="fmi-edge" data-testid="fleet-mission-edge" data-kind={seq ? "sequenced" : "depends"} data-from={d} data-to={p.id}>
        <title>{seq ? seq.because : `part ${p.id} starts after part ${d} is done`}</title>
        <path d={`M${x1} ${y1} C${x1 + bend} ${y1} ${x2 + bend} ${y2} ${x2} ${y2}`} />
        <g className={seq ? "fmi-seq-chip" : "fmi-hand-chip"} data-testid={seq ? "fleet-mission-seq-chip" : "part-edge-label"} data-from={d} data-to={p.id}
           transform={`translate(${mx - cw / 2} ${my - 8})`}>
          <rect width={cw} height={16} rx={8} />
          <text x={cw / 2} y={11.5} textAnchor="middle">{label}</text>
        </g>
      </g>,
    ];
  });
}
