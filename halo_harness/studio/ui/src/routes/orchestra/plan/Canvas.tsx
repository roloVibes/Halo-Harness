// The plan canvas (3.0.9.0 R2; data-testid plan-canvas): the planned lanes
// as cards in their DAG layer boxes (layout.ts), the `after` edges with their
// label chips. Drag a card into another box: box 1 clears what it runs after,
// box k makes it run after the lanes of box k-1, the empty last box opens a
// new layer. A click selects a card for the inspector. Click the canvas,
// then Ctrl+Z / Ctrl+Shift+Z undo and redo. 3.1.2.0 R2: each card carries
// its lane's cost chip (the forecast in the plan store).
import { useCallback, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { layerMap, moveToLayer, redo, undo } from "./actions";
import { boxAt, layout } from "./layout";
import { Edges, LaneCard, LayerBox, type PlanEdge } from "./Parts";
import { byJob } from "./forecast";
import { edgeLabel, NO_JOBS, plan, problemsOf, selectLane, upstreams, usePlan } from "./store";

type Drag = { id: string; dx: number; dy: number; hot: number | null };

export function PlanCanvas() {
  const jobs = usePlan((s) => s.jobs || NO_JOBS);
  const problems = usePlan((s) => s.problems);
  const sel = usePlan((s) => s.sel);
  const forecast = usePlan((s) => s.forecast);
  const costs = useMemo(() => byJob(forecast), [forecast]);
  const [drag, setDrag] = useState<Drag | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const layer = useMemo(() => layerMap(jobs), [jobs]);
  const laid = useMemo(() => layout(jobs.map((j) => j.id), layer, true), [jobs, layer]);
  const edges = useMemo<PlanEdge[]>(() => {
    const ids = new Set(jobs.map((j) => j.id));
    return jobs.flatMap((j) => upstreams(j).filter((u) => ids.has(u) && u !== j.id).map((u) => ({ from: u, to: j.id, label: edgeLabel(j, u) })));
  }, [jobs]);
  const pos = useMemo(
    () => (drag && laid.pos[drag.id] ? { ...laid.pos, [drag.id]: { x: laid.pos[drag.id].x + drag.dx, y: laid.pos[drag.id].y + drag.dy } } : laid.pos),
    [laid, drag],
  );

  const world = (ev: { clientX: number; clientY: number }) => {
    const r = scroll.current!.getBoundingClientRect();
    return { x: ev.clientX - r.left + scroll.current!.scrollLeft, y: ev.clientY - r.top + scroll.current!.scrollTop };
  };

  const onDown = useCallback((ev: PointerEvent<HTMLElement>, id: string) => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    scroll.current?.focus({ preventScroll: true });
    const x0 = ev.clientX, y0 = ev.clientY;
    let moved = false;
    let last: Drag = { id, dx: 0, dy: 0, hot: null };
    const boxes = () => layout(plan.get().jobs.map((j) => j.id), layerMap(plan.get().jobs), true).boxes;
    const move = (m: globalThis.PointerEvent) => {
      const dx = m.clientX - x0, dy = m.clientY - y0;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      const p = world(m);
      last = { id, dx, dy, hot: boxAt(boxes(), p.x, p.y) };
      setDrag(last);
    };
    const up = (u: globalThis.PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setDrag(null);
      if (!moved) return selectLane(id);
      const p = world(u);
      const k = boxAt(boxes(), p.x, p.y);
      const now = layerMap(plan.get().jobs)[id] || 0;
      if (k !== null && k !== now) moveToLayer(id, k);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "z") (e.shiftKey ? redo() : undo(), e.preventDefault());
    else if (mod && e.key.toLowerCase() === "y") (redo(), e.preventDefault());
  };

  const label = (k: number) => {
    if (k === 0) return "at once";
    const ups = [...new Set(laid.columns[k].flatMap((id) => upstreams(jobs.find((j) => j.id === id)!)))];
    return `after ${(ups.length ? ups : laid.columns[k - 1]).join(", ")}`;
  };
  const index = new Map(jobs.map((j, i) => [j.id, i + 1]));
  return (
    <div className="rc-scroll pc-scroll" ref={scroll} tabIndex={0} onKeyDown={onKey} data-testid="plan-canvas" data-layers={laid.columns.filter((c) => c.length).length}
         onPointerDown={(e) => e.target === e.currentTarget && selectLane("")} aria-label="The plan: lanes in their layer boxes">
      <div className="rc-world" style={{ width: laid.w, height: laid.h }}>
        {laid.boxes.map((b, k) => (
          <LayerBox key={k} k={k} b={b} label={label(k)} count={laid.columns[k].length} empty={!laid.columns[k].length} hot={drag?.hot === k} />
        ))}
        <Edges edges={edges} pos={pos} w={laid.w} h={laid.h} sel={sel} />
        {jobs.map((j) => (
          <LaneCard key={j.id} job={j} n={index.get(j.id) || 0} p={pos[j.id] || { x: 0, y: 0 }} layer={layer[j.id] || 0} problems={problemsOf(problems, j.id)}
                    selected={j.id === sel} dragging={drag?.id === j.id} cost={costs[j.id]} onDown={onDown} />
        ))}
      </div>
    </div>
  );
}
