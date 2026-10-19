// The timeline strip of fleet-activity: one lane per live agent over the
// last 5, 15 or 60 minutes; a bar per state in its colour (working cyan,
// waiting / paused amber, done green, failed red, queued faint), each tool
// call a tick; hover says who, what and when; a click selects that agent on
// the map (and the Agent panel follows). Drawn in SVG from the lanes and
// ticks the panels' store keeps (pload.ts). 3.1.4.0 R1: drawn at its real
// width (one SVG unit per px), so the lane names keep their size and their
// 116 px column in a narrow Activity panel instead of shrinking with it.
// 3.1.4.0 R2: the lanes of the agents in scope only (scope.ts: Session's
// harness, or its chosen session).
import { useEffect, useMemo, useRef, useState, type MouseEvent, type RefObject } from "react";
import { select } from "./actions";
import { panels, usePanels, type Seg } from "./pstore";
import { sessionsIn, useScope } from "./scope";
import { allAgents, isLive, sessionTitle, useFleet, useNow } from "./store";

const LANE = 18;
const LABEL_W = 116;
const MIN_W = 300;
const SPANS = [5, 15, 60] as const;

/** The strip's drawable width in px (its box minus the padding), followed as the panel resizes. */
function useWidth(): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setW(Math.max(MIN_W, Math.floor(el.clientWidth - 12)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

type Tip = { x: number; y: number; text: string } | null;

function hhmm(ms: number): string {
  const d = new Date(ms);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

/** The bars of one lane inside [from, to]: each segment from its start to the next one's (or now). */
function bars(segs: Seg[], from: number, to: number): { x0: number; x1: number; state: string; t: number }[] {
  const out = [];
  for (let i = 0; i < segs.length; i++) {
    const a = Math.max(from, segs[i].t);
    const b = Math.min(to, i + 1 < segs.length ? segs[i + 1].t : to);
    if (b > a) out.push({ x0: a, x1: b, state: segs[i].state, t: segs[i].t });
  }
  return out;
}

export function Timeline() {
  const harnesses = useFleet((s) => s.harnesses);
  const selected = useFleet((s) => s.selected);
  const lanes = usePanels((s) => s.lanes);
  const ticks = usePanels((s) => s.ticks);
  const span = usePanels((s) => s.span);
  const now = useNow(true, 1000);
  const [tip, setTip] = useState<Tip>(null);
  const [wrap, W] = useWidth();
  const scope = useScope();
  const live = useMemo(() => allAgents({ harnesses: sessionsIn(harnesses, scope) } as never).filter((r) => isLive(r.a)), [harnesses, scope]);
  const from = now - span * 60_000;
  const x = (t: number) => LABEL_W + ((t - from) / (now - from)) * (W - LABEL_W - 4);
  const height = Math.max(1, live.length) * LANE + 18;
  const hover = (e: MouseEvent, text: string) => {
    const box = (e.currentTarget as SVGElement).ownerSVGElement?.getBoundingClientRect();
    if (box) setTip({ x: e.clientX - box.left + 10, y: e.clientY - box.top + 12, text });
  };
  return (
    <div className="ftl" data-testid="fleet-timeline">
      <div className="ftl-bar">
        <span className="rail-label mono">TIMELINE · ONE LANE PER LIVE AGENT</span>
        <span className="spacer" />
        <div className="segmented" role="group" aria-label="How far back">
          {SPANS.map((m) => (
            <button key={m} className={span === m ? "on" : ""} aria-pressed={span === m} onClick={() => panels.update(() => ({ span: m }))} data-testid={`fleet-span-${m}`}>
              {m} min
            </button>
          ))}
        </div>
      </div>
      <div className="ftl-wrap" ref={wrap} onMouseLeave={() => setTip(null)}>
        <svg className="ftl-svg" viewBox={`0 0 ${W} ${height}`} width={W} height={height} role="img" aria-label="Agent timeline">
          {[0, 0.25, 0.5, 0.75, 1].map((k) => {
            const t = from + k * (now - from);
            return (
              <g key={k} className="ftl-grid">
                <line x1={x(t)} x2={x(t)} y1={0} y2={height - 14} />
                <text x={x(t)} y={height - 3} textAnchor={k === 0 ? "start" : k === 1 ? "end" : "middle"}>{k === 1 ? "now" : `-${Math.round((1 - k) * span)}m`}</text>
              </g>
            );
          })}
          {!live.length && <text className="ftl-none" x={LABEL_W} y={13}>no agent is live: a lane appears when one starts</text>}
          {live.map((r, i) => {
            const y = i * LANE;
            const name = r.a.name || r.a.role || r.a.agent_id;
            const label = r.h.local ? name : `${name}@${(r.h.name || r.h.id).split("@")[0]}`;
            const where = `${r.h.name || r.h.id.slice(0, 8)} · ${sessionTitle(r.s)}`;
            return (
              <g key={r.key} className="ftl-lane" data-testid="fleet-lane" data-key={r.key} data-selected={r.key === selected || undefined} onClick={() => select(r.key)} role="button" aria-label={`${name}: select it on the map`}>
                <rect className="ftl-hit" x={0} y={y} width={W} height={LANE} />
                <text className="ftl-name" x={4} y={y + 12.5}>{label.length > 18 ? label.slice(0, 17) + "…" : label}</text>
                {bars(lanes[r.key] || [], from, now).map((b) => (
                  <rect key={b.t} className="ftl-seg" data-state={b.state} x={x(b.x0)} y={y + 4} width={Math.max(1.5, x(b.x1) - x(b.x0))} height={LANE - 8} rx={2}
                        onMouseMove={(e) => hover(e, `${name} · ${b.state} since ${hhmm(b.t)}\n${where}`)} />
                ))}
                {(ticks[r.key] || []).filter((t) => t >= from).map((t, j) => (
                  <line key={j} className="ftl-tick" x1={x(t)} x2={x(t)} y1={y + 1} y2={y + LANE - 1} onMouseMove={(e) => hover(e, `${name} · tool call at ${hhmm(t)}`)} />
                ))}
              </g>
            );
          })}
        </svg>
        {tip && <div className="ftl-tip mono" style={{ left: tip.x, top: tip.y }} data-testid="fleet-timeline-tip">{tip.text}</div>}
      </div>
    </div>
  );
}
