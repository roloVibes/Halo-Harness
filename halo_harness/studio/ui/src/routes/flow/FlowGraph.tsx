// A saved flow on the plan canvas (3.0.9.0 R2; data-testid flow-graph): its
// steps as cards (flow-step) in their dependency layers, from their
// `$.<step>` refs as GET flow/templates answers them (flows/graph.py), the
// confirm step marked as the gate. Read-only this round, except the order of
// independent steps: drag a card onto another one in the same box and the
// flow file is rewritten in that order (PUT flow/templates/<name> {order};
// a shipped template is copied to your ~/.halo/flows first). Opened from the
// intake's "Show as graph" (or ?graph=<name>); Back returns to the section.
import { useMemo, useRef, useState, type PointerEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { Button, Empty } from "../../lib/ui";
import { CARD_W, edgePath, layout, type Pos } from "../orchestra/plan/layout";
import { showGraph, useFlow } from "./store";
import { loadTemplates } from "./sync";

const CARD_H = 72;
type Step = { id: string; kind: string; uses?: string; deps?: string[]; layer?: number; gate?: boolean };

/** The new file order: `id` moved just before (or after) `target`. */
function moved(order: string[], id: string, target: string, after: boolean): string[] {
  const rest = order.filter((x) => x !== id);
  const at = rest.indexOf(target) + (after ? 1 : 0);
  return [...rest.slice(0, at), id, ...rest.slice(at)];
}

export function FlowGraphView({ name }: { name: string }) {
  const templates = useFlow((s) => s.templates);
  const t = templates.find((x) => x.name === name);
  const steps = (t?.steps || []) as Step[];
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number; hot: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const scroll = useRef<HTMLDivElement>(null);
  const layer = useMemo(() => Object.fromEntries(steps.map((s) => [s.id, s.layer || 0])), [steps]);
  const laid = useMemo(() => layout(steps.map((s) => s.id), layer, false, CARD_H), [steps, layer]);
  const edges = useMemo(() => {
    const used = new Set(steps.flatMap((s) => (s.kind === "done" ? [] : s.deps || [])));
    return steps.flatMap((s) => {
      const from = s.kind === "done" ? (s.deps || []).filter((d) => !used.has(d)) : s.deps || [];
      return from.map((d) => ({ from: d, to: s.id }));
    });
  }, [steps]);
  const at = (p: Pos, except: string) =>
    steps.find((s) => s.id !== except && laid.pos[s.id] && p.x >= laid.pos[s.id].x && p.x <= laid.pos[s.id].x + CARD_W && p.y >= laid.pos[s.id].y && p.y <= laid.pos[s.id].y + CARD_H);
  const world = (ev: { clientX: number; clientY: number }): Pos => {
    const r = scroll.current!.getBoundingClientRect();
    return { x: ev.clientX - r.left + scroll.current!.scrollLeft, y: ev.clientY - r.top + scroll.current!.scrollTop };
  };
  const save = async (order: string[]) => {
    setBusy(true);
    try {
      const r = await api.put<{ path: string }>(`flow/templates/${encodeURIComponent(name)}`, { order });
      toast(`Saved the new order to ${r.path}`, "done");
      await loadTemplates();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e), "error", 5000);
    }
    setBusy(false);
  };
  const onDown = (ev: PointerEvent<HTMLElement>, id: string) => {
    if (ev.button !== 0 || busy) return;
    ev.preventDefault();
    const x0 = ev.clientX, y0 = ev.clientY;
    let last = { id, dx: 0, dy: 0, hot: "" };
    const move = (m: globalThis.PointerEvent) => {
      const p = world(m), over = at(p, id);
      last = { id, dx: m.clientX - x0, dy: m.clientY - y0, hot: over && layer[over.id] === layer[id] ? over.id : "" };
      setDrag(last);
    };
    const up = (u: globalThis.PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setDrag(null);
      if (!last.hot) return;
      const p = world(u), target = laid.pos[last.hot];
      void save(moved(steps.map((s) => s.id), id, last.hot, p.y > target.y + CARD_H / 2));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const pos = drag ? { ...laid.pos, [drag.id]: { x: laid.pos[drag.id].x + drag.dx, y: laid.pos[drag.id].y + drag.dy } } : laid.pos;
  return (
    <div className="fg" data-testid="flow-graph" data-flow={name}>
      <div className="fg-bar">
        <b className="fg-title mono">{name}</b>
        {t && <span className="og-chip mono">{t.source}</span>}
        <span className="mono muted">{steps.length} steps · {laid.columns.length} layers</span>
        <span className="spacer" />
        <Button size="sm" onClick={() => showGraph("")} data-testid="flow-graph-back">Back to the flow</Button>
      </div>
      {!t ? (
        <Empty title={`No flow called ${name}`} body="Pick a flow in the intake form, then Show as graph." />
      ) : (
        <div className="rc-scroll pc-scroll" ref={scroll} aria-label={`The ${name} flow's steps in their dependency layers`}>
          <div className="rc-world" style={{ width: laid.w, height: laid.h }}>
            {laid.boxes.map((b, k) => (
              <div key={k} className="rc-tier pc-layer" data-testid="flow-graph-layer" data-index={k === 0 ? 0 : undefined} style={{ left: b.x, top: b.y, width: b.w, height: b.h }}>
                <div className="rc-tier-head pc-layer-head">
                  <span className="rc-tier-label">{k === 0 ? "first" : `after ${laid.columns[k - 1].join(", ")}`}</span>
                  <span className="rc-tier-count mono">{laid.columns[k].length}</span>
                </div>
              </div>
            ))}
            <svg className="rc-edges" width={laid.w} height={laid.h} aria-hidden="true">
              {edges.map((e) => pos[e.from] && pos[e.to] && <path key={`${e.from}>${e.to}`} className="rc-edge pc-edge" d={edgePath(pos[e.from], pos[e.to], CARD_H).d} data-testid="flow-graph-edge" />)}
            </svg>
            {steps.map((s, i) => (
              <article key={s.id} className="rc-card pc-card fg-card" data-testid="flow-step" data-id={s.id} data-kind={s.kind} data-layer={s.layer || 0}
                       data-gate={s.gate || undefined} data-hot={drag?.hot === s.id || undefined} data-dragging={drag?.id === s.id || undefined} data-lc={String(i % 10)}
                       style={{ left: pos[s.id]?.x ?? 0, top: pos[s.id]?.y ?? 0, width: CARD_W, height: CARD_H }} onPointerDown={(ev) => onDown(ev, s.id)}
                       title={s.gate ? "The human gate: the run waits here for your OK" : "Drag onto another step in the same box to change their order"}>
                <span className="rc-band" aria-hidden="true" />
                <header className="rc-head">
                  <b className="mono pc-id">{s.id}</b>
                  <span className="rc-scope mono">{s.kind}</span>
                </header>
                <div className="pc-title mono muted">{s.gate ? <span className="fg-gate">◆ gate · waits for you</span> : s.uses || "-"}</div>
                <div className="rc-meta mono">{(s.deps || []).length ? `reads ${(s.deps || []).join(", ")}` : "reads nothing"}</div>
              </article>
            ))}
          </div>
        </div>
      )}
      <p className="fg-note muted">Read-only for now: drag a step onto another one in the same box (they do not read each other) to change their order in the flow file.</p>
    </div>
  );
}
