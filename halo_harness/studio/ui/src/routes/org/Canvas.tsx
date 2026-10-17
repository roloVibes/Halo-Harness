// org-chart (3.0.7.0 R3; the drawn canvas is data-testid org-canvas): the company as cards in group boxes (layout.ts),
// the reports-to lines between them. Drag a card to move it (the position is
// saved to the server 500 ms after the last move); drop it into another box,
// or onto a card, and Studio asks before it changes who it reports to in
// Paperclip. Drag a box by its label strip to move the whole group. Click a
// card to select it, double-click to open the Inspector on it. A lays the
// canvas out, F fits it, + and - zoom (click the canvas first).
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Empty } from "../../lib/ui";
import { focusPanel, patchPanel } from "../../lib/workspace/persist";
import { Metric } from "../orchestra/bits";
import { setOrgMode } from "./actions";
import { Card, Edges, GroupBox } from "./CanvasParts";
import { autoLayout, dropTarget, extent, groupsOf, placeAll, type Group } from "./layout";
import { agentById, openDialog, org, select, useOrg } from "./store";
import { movePositions } from "./sync";
import type { Pos } from "./types";

type Drag = { ids: string[]; dx: number; dy: number; card: string; hot: string };

export function openInspector(): void {
  patchPanel("org", "org-inspector", { collapsed: false, face: "detail" }, false);
  focusPanel("org", "org-inspector");
}

function Toolbar({ zoom, setZoom, fit, layout }: { zoom: number; setZoom: (z: number) => void; fit: () => void; layout: () => void }) {
  const st = useOrg((s) => s.status);
  const company = useOrg((s) => s.company);
  const n = useOrg((s) => s.agents.length);
  return (
    <div className="oc-bar">
      <span className="mono muted oc-count">{company?.name || "company"} · {n} agent{n === 1 ? "" : "s"}</span>
      {st && !st.enabled && (
        <span className="oc-off" data-testid="org-mode-off">
          Org mode is off: no heartbeats run.
          <Button size="sm" variant="ghost" onClick={() => void setOrgMode(true)}>Turn it on</Button>
        </span>
      )}
      <span className="spacer" />
      <Button size="sm" variant="ghost" onClick={layout} title="Lay the cards out by level (A)">Lay out</Button>
      <Button size="sm" variant="ghost" onClick={fit} title="Fit the canvas to the panel (F)">Fit</Button>
      <span className="segmented oc-zoom" role="group" aria-label="Zoom">
        <button onClick={() => setZoom(Math.max(0.3, zoom / 1.2))} aria-label="Zoom out">-</button>
        <button onClick={() => setZoom(1)} title="Back to 100%">{Math.round(zoom * 100)}%</button>
        <button onClick={() => setZoom(Math.min(2, zoom * 1.2))} aria-label="Zoom in">+</button>
      </span>
    </div>
  );
}

export function CanvasDetail() {
  const agents = useOrg((s) => s.agents);
  const saved = useOrg((s) => s.positions);
  const selId = useOrg((s) => (s.sel?.kind === "agent" ? s.sel.id : ""));
  const loaded = useOrg((s) => s.loaded);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [zoom, setZoom] = useState(1);
  const scroll = useRef<HTMLDivElement>(null);
  const groups = useMemo(() => groupsOf(agents), [agents]);
  const placed = useMemo(() => placeAll(agents, saved, groups), [agents, saved, groups]);
  const pos = useMemo(() => {
    if (!drag) return placed;
    const out = { ...placed };
    for (const id of drag.ids) out[id] = { x: placed[id].x + drag.dx, y: placed[id].y + drag.dy };
    return out;
  }, [placed, drag]);
  const ext = extent(placed);
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  const world = (ev: { clientX: number; clientY: number }): Pos => {
    const r = scroll.current!.getBoundingClientRect();
    return { x: (ev.clientX - r.left + scroll.current!.scrollLeft) / zoomRef.current, y: (ev.clientY - r.top + scroll.current!.scrollTop) / zoomRef.current };
  };

  /** Drag `ids` together; `card` is the one card a drop can re-parent. */
  const begin = useCallback((ev: PointerEvent<HTMLElement>, ids: string[], card: string) => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    scroll.current?.focus({ preventScroll: true });
    const x0 = ev.clientX, y0 = ev.clientY;
    let moved = false;
    let last: Drag = { ids, dx: 0, dy: 0, card, hot: "" };
    const move = (m: globalThis.PointerEvent) => {
      const dx = (m.clientX - x0) / zoomRef.current, dy = (m.clientY - y0) / zoomRef.current;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      let hot = "";
      if (card) {
        const s = org.get();
        const t = dropTarget(groupsOf(s.agents), placeAll(s.agents, s.positions, groupsOf(s.agents)), card, world(m));
        hot = t.group ? t.group.key : "";
      }
      last = { ids, dx, dy, card, hot };
      setDrag(last);
    };
    const up = (u: globalThis.PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setDrag(null);
      if (!moved) {
        if (card) select({ kind: "agent", id: card });
        return;
      }
      const s = org.get();
      const all = placeAll(s.agents, s.positions, groupsOf(s.agents));
      const next: Record<string, Pos> = {};
      for (const id of ids) next[id] = { x: Math.max(0, all[id].x + last.dx), y: Math.max(0, all[id].y + last.dy) };
      if (!card) return movePositions(next);
      const a = agentById(s, card)!;
      const t = dropTarget(groupsOf(s.agents), all, card, world(u));
      const boss = t.card ?? (t.group ? t.group.manager || null : undefined);
      movePositions(next);
      if (boss === undefined || boss === (a.reportsTo || null) || boss === card) return;
      openDialog({ kind: "reparent", agent: card, boss, back: all[card] });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  const onCard = useCallback((ev: PointerEvent<HTMLElement>, id: string) => begin(ev, [id], id), [begin]);
  const onGroup = useCallback((ev: PointerEvent<HTMLElement>, g: Group) => begin(ev, g.members.map((a) => a.id), ""), [begin]);
  const onOpen = useCallback((id: string) => (select({ kind: "agent", id }), openInspector()), []);
  const fit = () => {
    const el = scroll.current;
    if (el) setZoom(Math.max(0.3, Math.min(1.25, (el.clientWidth - 24) / ext.w, (el.clientHeight - 24) / ext.h)));
  };
  const layout = () => movePositions(autoLayout(groupsOf(org.get().agents)));
  const company = useOrg((s) => s.company?.id || "");
  const fitted = useRef("");
  useEffect(() => {
    // the first time a company draws: fit it when it is wider or taller than the panel
    const el = scroll.current;
    if (!el || !agents.length || fitted.current === company) return;
    fitted.current = company;
    if (ext.w > el.clientWidth || ext.h > el.clientHeight) setZoom(Math.max(0.3, Math.min(1, (el.clientWidth - 24) / ext.w, (el.clientHeight - 24) / ext.h)));
  }, [company, agents.length, ext.w, ext.h]);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === "a") layout();
    else if (k === "f") fit();
    else if (k === "+" || k === "=") setZoom((z) => Math.min(2, z * 1.2));
    else if (k === "-") setZoom((z) => Math.max(0.3, z / 1.2));
    else return;
    e.preventDefault();
  };

  if (!loaded) return <div className="og-wait mono muted">reading the company...</div>;
  if (!agents.length)
    return <Empty title="No agents in this company yet" body="Sync a lineup into it from the Company panel (or the palette: Org: sync): one Paperclip agent per assignment." />;
  return (
    <div className="oc" data-testid="org-canvas">
      <Toolbar zoom={zoom} setZoom={setZoom} fit={fit} layout={layout} />
      <div className="oc-scroll" ref={scroll} tabIndex={0} onKeyDown={onKey} aria-label="Org canvas: agents boxed by who they report to">
        <div className="oc-world" style={{ width: ext.w * zoom, height: ext.h * zoom }}>
          <div className="oc-inner" style={{ width: ext.w, height: ext.h, transform: `scale(${zoom})` }}>
            {groups.map((g) => <GroupBox key={g.key} g={g} pos={pos} hot={drag?.hot === g.key} onDown={onGroup} />)}
            <Edges agents={agents} pos={pos} w={ext.w} h={ext.h} sel={selId} />
            {agents.map((a) => (
              <Card key={a.id} a={a} x={pos[a.id].x} y={pos[a.id].y} selected={a.id === selId} dragging={!!drag?.ids.includes(a.id)} onDown={onCard} onOpen={onOpen} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function CanvasGlance() {
  const n = useOrg((s) => s.agents.length);
  const running = useOrg((s) => s.agents.filter((a) => a.status === "running").length);
  const groups = useOrg((s) => groupsOf(s.agents).length);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={n} label="agents" />
        <Metric value={running} label="running" tone={running ? "accent" : undefined} />
        <Metric value={groups} label="teams" />
      </div>
      <div className="glance-hint">Expand for the org chart: one box per team.</div>
    </div>
  );
}

export function useCanvasMotion(): MotionState {
  const error = useOrg((s) => !!s.error);
  const running = useOrg((s) => s.agents.some((a) => a.status === "running"));
  const any = useOrg((s) => s.agents.length > 0);
  if (error) return "error";
  return running ? "working" : any ? "idle" : "none";
}
