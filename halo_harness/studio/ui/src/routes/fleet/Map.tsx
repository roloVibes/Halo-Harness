// fleet-map: every harness as a labelled group box (the canvases' group-box
// vocabulary; this harness first), its sessions as cards, each session's
// agents as a tree under it, laid out in code (layout.ts). By project
// regroups the cards into one box per repo with the harness colour on each.
// Click selects (fleet-agent and an open Inspector follow), double-click
// opens fleet-agent expanded, `...` is the node's menu. An edge lights for
// LIT_MS when an agent spawns or messages another (D13). R4: two agents of
// different sessions editing one file (GET fleet/conflicts) are joined by an
// amber dashed warning edge; its attention row's O opens the map on them.
// 3.0.6.0 R8: the open mission's plan is drawn over it (MapMission.tsx).
// 3.1.4.0 R2: under a scope (scope.ts, the Session section) it draws only
// that harness's box, By harness, with no mission over it.
import { useMemo, useRef, useState } from "react";
import { useRecent, type MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { short } from "../orchestra/format";
import { toggleByProject } from "./actions";
import { layout } from "./layout";
import { BoxChips, chipsWidth, useBoxChips } from "./MapChips";
import { MissionChip, MissionLayer, useMissionSlots } from "./MapMission";
import { AgentNode, NodeMenu, SessionCard, type MenuAt } from "./MapNode";
import { useAttnCount, usePanels } from "./pstore";
import { isScoped, useScope, useScopedAttention, useScopedCounts, useScopedHarnesses } from "./scope";
import { NONE, useFleet } from "./store";
import type { LitEdge } from "./types";

const LIT_MS = 3000;

function LitEdges({ edges, pos }: { edges: LitEdge[]; pos: Map<string, { x: number; y: number; w: number; h: number }> }) {
  const last = edges.length ? edges[edges.length - 1].ts : 0;
  const fresh = useRecent(last, LIT_MS);
  if (!fresh) return null;
  const now = Date.now();
  return (
    <g className="fm-lit-edges">
      {edges.filter((e) => now - e.ts < LIT_MS).map((e) => {
        const a = pos.get(e.from), b = pos.get(e.to);
        if (!a || !b) return null;
        const x1 = a.x + a.w - 6, y1 = a.y + a.h / 2, x2 = b.x + b.w - 6, y2 = b.y + b.h / 2;
        const bend = Math.max(28, Math.abs(y2 - y1) / 3);
        return <path key={`${e.from}>${e.to}@${e.ts}`} className="fm-edge fm-edge-lit" data-kind={e.kind} data-testid="fleet-lit-edge" d={`M${x1} ${y1} C${x1 + bend} ${y1} ${x2 + bend} ${y2} ${x2} ${y2}`} />;
      })}
    </g>
  );
}

type Pos = Map<string, { x: number; y: number; w: number; h: number }>;

function ConflictEdges({ pos }: { pos: Pos }) {
  const list = usePanels((s) => s.conflicts?.conflicts) || NONE;
  return (
    <g className="fm-conflicts">
      {list.map((c) => {
        const a = pos.get(c.a.key), b = pos.get(c.b.key);
        if (!a || !b) return null;
        const left = a.x <= b.x ? a : b, right = left === a ? b : a;
        const x1 = left.x + left.w, y1 = left.y + left.h / 2, x2 = right.x === left.x ? right.x + right.w : right.x, y2 = right.y + right.h / 2;
        const bend = right.x === left.x ? 46 : Math.max(24, (x2 - x1) / 2);
        const d = right.x === left.x ? `M${x1} ${y1} C${x1 + bend} ${y1} ${x2 + bend} ${y2} ${x2} ${y2}` : `M${x1} ${y1} C${x1 + bend} ${y1} ${x2 - bend} ${y2} ${x2} ${y2}`;
        return (
          <path key={c.id} className="fm-edge fm-edge-conflict" d={d} data-testid="fleet-conflict-edge" data-file={c.file}>
            <title>{`${c.a.name} (${c.a.harness_name}) and ${c.b.name} (${c.b.harness_name}) are both editing ${c.repo}/${c.file}`}</title>
          </path>
        );
      })}
    </g>
  );
}

export function FleetMap() {
  const harnesses = useScopedHarnesses();
  const scoped = isScoped(useScope());
  const byProject = useFleet((s) => s.byProject) && !scoped;
  const selected = useFleet((s) => s.selected);
  const edges = useFleet((s) => s.edges || NONE);
  const [menu, setMenu] = useState<MenuAt | null>(null);
  const { chips, focus } = useBoxChips(); // 3.0.6.0 R6: capability chips; the harness Who picked
  const slots = useMissionSlots(byProject || scoped); // 3.0.6.0 R8: the open mission's parts (none under a scope)
  const svg = useRef<SVGSVGElement>(null);
  const geo = useMemo(() => layout(harnesses, byProject, slots), [harnesses, byProject, slots]);
  const pos = useMemo(() => new Map(geo.nodes.map((n) => [n.ref.key, n])), [geo]);
  return (
    <>
    <svg ref={svg} className="fm-svg" viewBox={`0 0 ${geo.width} ${geo.height}`} width={geo.width} height={geo.height} role="img" aria-label="Fleet map" data-testid="fleet-map-svg">
      {geo.boxes.map((b) => {
        const bc = b.key.startsWith("h:") ? chips.get(b.key.slice(2)) || [] : [];
        const cw = chipsWidth(bc);
        return (
        <g key={b.key} className="fm-box" data-testid="fleet-box" data-key={b.key} data-online={b.online || undefined} data-local={b.local || undefined} data-hc={b.hc || undefined}
           data-who={(b.key === "h:" + focus && !!focus) || undefined}>
          <rect className="fm-box-shape" x={b.x} y={b.y} width={b.w} height={b.h} rx={16} />
          <rect className="fm-box-head" x={b.x} y={b.y} width={b.w} height={34} rx={14} />
          <circle className="fm-box-dot" cx={b.x + 16} cy={b.y + 17} r={4} />
          <text className="fm-box-label" x={b.x + 28} y={b.y + 21}>{b.label}</text>
          <text className="fm-box-sub" x={b.x + b.w - 14 - cw} y={b.y + 21} textAnchor="end">{short(b.sub, Math.max(0, Math.floor((b.w - 44 - cw - b.label.length * 9) / 6.4)))}</text>
          {bc.length > 0 && <BoxChips chips={bc} right={b.x + b.w - 10} cy={b.y + 17} />}
          {b.empty && <text className="fm-sub" x={b.x + 16} y={b.y + 62 + b.lane}>{b.key === "h:" ? "" : "no session here right now"}</text>}
        </g>
        );
      })}
      {geo.edges.map((e) => (
        <path key={e.to} className="fm-edge" data-on={e.to === selected || e.from === selected || undefined} d={e.d} />
      ))}
      {geo.cards.map((c) => <SessionCard key={c.harness.id + c.session.session_id} c={c} onMenu={setMenu} byProject={byProject} />)}
      {geo.nodes.map((n) => <AgentNode key={n.ref.key} n={n} onMenu={setMenu} />)}
      <LitEdges edges={edges} pos={pos} />
      <ConflictEdges pos={pos} />
      <MissionLayer geo={geo} svg={svg} />
    </svg>
    {menu && <NodeMenu at={menu} onClose={() => setMenu(null)} />}
    </>
  );
}

function Toolbar() {
  const byProject = useFleet((s) => s.byProject);
  const scoped = isScoped(useScope());
  const c = useScopedCounts();
  const every = useAttnCount(c.attention);
  const mine = useScopedAttention().count;
  const attn = scoped ? mine : every;
  return (
    <div className="fm-bar">
      {!scoped && (
        <div className="segmented" role="group" aria-label="Group the map">
          <button className={byProject ? "" : "on"} aria-pressed={!byProject} onClick={() => byProject && toggleByProject()}>By harness</button>
          <button className={byProject ? "on" : ""} aria-pressed={byProject} onClick={() => !byProject && toggleByProject()} data-testid="fleet-by-project">By project</button>
        </div>
      )}
      <span className="mono muted fm-counts">
        {scoped ? "this harness" : `${c.harnesses} harness${c.harnesses === 1 ? "" : "es"}`} · {c.sessions} session{c.sessions === 1 ? "" : "s"} · {c.live} of {c.agents} agents live
        {attn > 0 && <b className="fm-attn"> · {attn} need{attn === 1 ? "s" : ""} you</b>}
      </span>
      {!scoped && <MissionChip byProject={byProject} />}
    </div>
  );
}

export function MapDetail() {
  const loaded = useFleet((s) => s.loaded);
  const error = useFleet((s) => s.error);
  const any = useFleet((s) => s.harnesses.length);
  if (!loaded) return <div className="og-wait mono muted">reading the fleet...</div>;
  if (error && !any) return <Empty title="Studio could not read the fleet" body={error} />;
  return (
    <div className="fm">
      <Toolbar />
      <div className="fm-scroll">
        <FleetMap />
      </div>
    </div>
  );
}

export function MapGlance() {
  const c = useScopedCounts();
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={c.harnesses} label="harnesses" />
        <Metric value={c.live} label="agents live" tone="accent" />
        <Metric value={c.attention} label="need you" tone={c.attention ? "warn" : undefined} />
      </div>
      <div className="glance-hint">Expand for the map: every harness, session and agent.</div>
    </div>
  );
}

export function useMapMotion(): MotionState {
  const c = useScopedCounts();
  const error = useFleet((s) => !!s.error);
  if (error) return "error";
  if (c.attention) return "waiting";
  return c.live ? "working" : c.harnesses ? "idle" : "none";
}
