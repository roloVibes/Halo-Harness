// The open mission's plan drawn over the Fleet map (3.0.6.0 R8): each part
// a node in its harness box's lane (dashed while planned, solid once it
// runs, the motion vocabulary's colours: amber asked, cyan running, green
// done, red failed), an edge for each depends_on, amber with a chip where
// two parts were put one after the other because their claims overlap (any
// other edge a chip naming what it hands on, 3.0.9.0), a repo part's base, a
// red chip on a part nobody can run, a lock on one pinned by capability.
// Drag a part's node into another harness box to move it there (the route
// checks it in code; a 422 snaps it back with the reason in a toast). A
// click picks the part (its table row lights).
import { useMemo, useRef, useState, type PointerEvent as PE, type ReactElement, type RefObject } from "react";
import { short } from "../orchestra/format";
import type { Geometry, PartBox, PartSlot } from "./layout";
import { EDITABLE, missions, partMotion, partState, useMissions, usd, type PlanPart, type View } from "./mstore";
import { reassign } from "./mload";
import { partAgent } from "./MissionRun";
import { useFleet } from "./store";

const fit = (text: string, px: number) => short(text, Math.max(4, Math.floor(px / 6.4)));

/** The parts to place on the map: the open mission's plan, By harness only. */
export function useMissionSlots(byProject: boolean): PartSlot[] | undefined {
  const plan = useMissions((s) => s.view?.plan);
  return useMemo(() => (byProject || !plan?.parts.length ? undefined : plan.parts.map((p) => ({ id: p.id, harness: p.harness }))), [plan, byProject]);
}

function Lock({ x, y, title }: { x: number; y: number; title: string }) {
  return (
    <g className="fmi-lock" transform={`translate(${x} ${y})`} data-testid="fleet-part-lock">
      <title>{title}</title>
      <rect x={1} y={5} width={8} height={6} rx={1.2} />
      <path d="M3 5V3.6a2 2 0 0 1 4 0V5" />
    </g>
  );
}

type Off = { dx: number; dy: number };

function PartNode({ b, p, v, geo, svg }: { b: PartBox; p: PlanPart; v: View; geo: Geometry; svg: RefObject<SVGSVGElement | null> }) {
  const sel = useMissions((s) => s.selPart === p.id);
  const held = useMissions((s) => (s.drag?.part === p.id ? s.drag : null));
  const harnesses = useFleet((s) => s.harnesses);
  const [off, setOff] = useState<Off | null>(null);
  const start = useRef<{ x: number; y: number; k: number; moved: boolean; dx: number; dy: number } | null>(null);
  const st = partState(v, p.id);
  const editable = EDITABLE.includes(v.mission.state);
  const o = held || off;
  const down = (e: PE<SVGGElement>) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    start.current = { x: e.clientX, y: e.clientY, k: svg.current?.getScreenCTM()?.a || 1, moved: false, dx: 0, dy: 0 };
  };
  const move = (e: PE<SVGGElement>) => {
    const s0 = start.current;
    if (!s0 || !editable) return;
    const dx = (e.clientX - s0.x) / s0.k, dy = (e.clientY - s0.y) / s0.k;
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
      return;
    }
    const cx = b.x + b.w / 2 + s0.dx, cy = b.y + b.h / 2 + s0.dy;
    const box = geo.boxes.find((x) => x.key.length > 2 && x.key.startsWith("h:") && cx >= x.x && cx <= x.x + x.w && cy >= x.y && cy <= x.y + x.h);
    const hid = box?.key.slice(2);
    if (box && hid && hid !== p.harness) {
      missions.update(() => ({ drag: { part: p.id, dx: s0.dx, dy: s0.dy, pending: true } }));
      void reassign(p.id, hid, box.label);
    }
    setOff(null);
  };
  const run = v.mission.parts?.[p.id];
  const live = st === "running" ? partAgent(harnesses, v.mission.id, p.id, run?.harness || p.harness) : null;
  const line = st === "asked" ? `waiting on ${run?.harness_name || p.harness_name || "its"} owner`
    : live ? String(live.agent.current || live.agent.last_text || "working") : p.unassignable ? p.unassignable : p.reason || p.brief;
  const chipW = p.unassignable ? 84 : 0;
  const base = partBase(v, p);
  return (
    <g className="fmi-node" data-testid="fleet-part" data-part={p.id} data-harness={p.harness || ""} data-state={st} data-motion={partMotion(st)}
       data-pinned={p.pinned || undefined} data-selected={sel || undefined} data-drag={o ? (held ? "pending" : "moving") : undefined} data-editable={editable || undefined}
       transform={`translate(${b.x + (o?.dx || 0)} ${b.y + (o?.dy || 0)})`} onPointerDown={down} onPointerMove={move} onPointerUp={up}
       onPointerCancel={() => ((start.current = null), setOff(null))} role="button" tabIndex={0} aria-label={`part ${p.id}: ${p.title}, ${st}`}>
      <title>{`part ${p.id}: ${p.title}\n${p.harness_name ? "on " + p.harness_name + (p.reason ? ": " + p.reason : "") : "no harness"}${editable ? "\ndrag it to another harness box to move it" : ""}`}</title>
      <rect className="fmi-node-shape" width={b.w} height={b.h} rx={8} />
      <circle className="fmi-node-dot" cx={12} cy={14} r={4} />
      <text className="fmi-node-id" x={22} y={18}>{p.id}</text>
      <text className="fmi-node-title" x={36} y={18}>{fit(p.title, b.w - 120 - chipW)}</text>
      <text className="fmi-node-sub" x={22} y={33}>{fit(line, b.w - 80 - (base ? 84 : 0))}</text>
      {base && <text className="fmi-node-base" data-testid="part-base" x={b.w - 66} y={33} textAnchor="end">{base}</text>}
      {p.pinned && <Lock x={b.w - 84 - chipW} y={6} title={`pinned: ${p.reason}`} />}
      {p.unassignable && (
        <g className="fmi-chip-bad" data-testid="fleet-part-unassignable" transform={`translate(${b.w - 86} 6)`}>
          <title>{p.unassignable}</title>
          <rect width={80} height={15} rx={7.5} />
          <text x={40} y={11} textAnchor="middle">unassignable</text>
        </g>
      )}
      <text className="fmi-node-cost" x={b.w - 10} y={33} textAnchor="end">{run?.cost_usd ? usd(run.cost_usd) : `est ${usd(p.est_cost_usd)}`}</text>
      <text className="fmi-node-kind" x={b.w - 10} y={17} textAnchor="end">{p.kind}</text>
    </g>
  );
}

function Edges({ v, pos }: { v: View; pos: Map<string, PartBox> }) {
  const out: ReactElement[] = [];
  for (const p of v.plan?.parts || []) {
    const b = pos.get(p.id);
    for (const d of p.depends_on) {
      const a = pos.get(d);
      if (!a || !b) continue;
      const seq = (p.sequenced || []).find((x) => x.after === d);
      const same = Math.abs(a.x - b.x) < 1;
      const x1 = same || a.x < b.x ? a.x + a.w : a.x, x2 = same ? b.x + b.w : a.x < b.x ? b.x : b.x + b.w;
      const y1 = a.y + a.h / 2, y2 = b.y + b.h / 2;
      const bend = same ? 34 + 8 * Math.abs(Number(p.id) - Number(d)) : (x2 - x1) / 2;
      const c1 = same ? x1 + bend : x1 + bend, c2 = same ? x2 + bend : x2 - bend;
      const mx = same ? x1 + bend * 0.75 : (x1 + x2) / 2, my = (y1 + y2) / 2;
      out.push(
        <g key={`${d}>${p.id}`} className="fmi-edge" data-testid="fleet-mission-edge" data-kind={seq ? "sequenced" : "depends"} data-from={d} data-to={p.id}>
          <title>{seq ? seq.because : `part ${p.id} starts after part ${d} is done`}</title>
          <path d={`M${x1} ${y1} C${c1} ${y1} ${c2} ${y2} ${x2} ${y2}`} markerEnd={seq ? "url(#fmi-arrow-seq)" : "url(#fmi-arrow)"} />
          {seq && (
            <g className="fmi-seq-chip" data-testid="fleet-mission-seq-chip" transform={`translate(${mx - 24} ${my - 8})`}>
              <rect width={48} height={16} rx={8} />
              <text x={24} y={11.5} textAnchor="middle">claims</text>
            </g>
          )}
          {!seq && <EdgeLabel v={v} part={p} dep={d} x={mx} y={my} />}
        </g>,
      );
    }
  }
  return <g className="fmi-edges">{out}</g>;
}

/** 3.0.9.0: what a depends_on edge carries: `all`, the dependency's outputs, or its hand-back. */
export function handoffLabel(v: View, part: PlanPart, dep: string): string {
  if (part.take === "all") return "all";
  const d = v.plan?.parts.find((x) => x.id === dep);
  const names = (d?.outputs || []).map((o) => o.split("/").pop() || o);
  return names.length ? names.join(", ") : "hand-back";
}

function EdgeLabel({ v, part, dep, x, y }: { v: View; part: PlanPart; dep: string; x: number; y: number }) {
  const label = short(handoffLabel(v, part, dep), 22);
  const w = 14 + label.length * 6;
  return (
    <g className="fmi-hand-chip" data-testid="part-edge-label" data-from={dep} data-to={part.id} transform={`translate(${x - w / 2} ${y - 8})`}>
      <title>{`part ${part.id} reads ${label} from part ${dep}${part.kind === "repo" ? " and starts from its finished branch when it changed the repo" : ""}`}</title>
      <rect width={w} height={16} rx={8} />
      <text x={w / 2} y={11.5} textAnchor="middle">{label}</text>
    </g>
  );
}

/** 3.0.9.0: where a repo part starts: its run's base, its repo dependencies' head, or the mission's base. */
export function partBase(v: View, p: PlanPart): string {
  if (p.kind !== "repo") return "";
  const run = v.mission.parts?.[p.id];
  if (run?.base) return `base ${run.base.slice(0, 7)}`;
  const deps = p.depends_on.filter((d) => v.plan?.parts.find((x) => x.id === d)?.kind === "repo");
  if (deps.length) return `base: ${deps.join("+")}'s head`;
  return v.mission.repo?.base ? `base ${v.mission.repo.base.slice(0, 7)}` : "";
}

/** The overlay itself (inside the map's SVG, over the boxes, under nothing). */
export function MissionLayer({ geo, svg }: { geo: Geometry; svg: RefObject<SVGSVGElement | null> }) {
  const v = useMissions((s) => s.view);
  const pos = useMemo(() => new Map(geo.parts.map((b) => [b.id, b])), [geo]);
  if (!v?.plan || !geo.parts.length) return null;
  const parts = new Map(v.plan.parts.map((p) => [p.id, p]));
  const heads = geo.boxes.filter((b) => b.lane > 0);
  return (
    <g className="fmi-layer" data-testid="fleet-mission-layer" data-mission={v.mission.id}>
      <defs>
        <marker id="fmi-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" className="fmi-arrow" /></marker>
        <marker id="fmi-arrow-seq" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" className="fmi-arrow-seq" /></marker>
      </defs>
      {heads.map((b) => (
        <g key={b.key} className="fmi-lane">
          <rect x={b.x + 8} y={b.y + 40} width={b.w - 16} height={b.lane - 6} rx={10} />
          <text x={b.x + 16} y={b.y + 53}>{`MISSION · ${geo.parts.filter((x) => "h:" + x.harness === b.key).length || "no"} PART${geo.parts.filter((x) => "h:" + x.harness === b.key).length === 1 ? "" : "S"} HERE`}</text>
        </g>
      ))}
      <Edges v={v} pos={pos} />
      {geo.parts.map((b) => {
        const p = parts.get(b.id);
        return p ? <PartNode key={b.id} b={b} p={p} v={v} geo={geo} svg={svg} /> : null;
      })}
    </g>
  );
}

/** The map toolbar's line about the plan on it (or why it is not drawn). */
export function MissionChip({ byProject }: { byProject: boolean }) {
  const v = useMissions((s) => s.view);
  if (!v?.plan) return null;
  return (
    <span className="mono fmi-mapchip" data-testid="fleet-mission-mapchip">
      mission {v.mission.state} · {v.plan.parts.length} parts{byProject ? " · drawn By harness only" : EDITABLE.includes(v.mission.state) ? " · drag a part to move it" : ""}
    </span>
  );
}
