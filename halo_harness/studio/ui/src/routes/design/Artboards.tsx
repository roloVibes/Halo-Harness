// design-artboards (3.0.7.0 R3): the open project's artboards as cards on a
// canvas (ArtboardCard.tsx). Drag a card by its title to move it; the
// places are saved on the server (`PUT layout/design:<slug>`) 500 ms after
// the last move, so they follow the project to any browser. A card with no
// saved place is flowed into rows. The toolbar: zoom, fit, Export (a
// dialog: folder, HTML, PNG, SVG or PDF) and Handoff (the bundle for the
// next session), each with its result dialog.
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { handoff } from "./actions";
import { ArtboardCard, CARD_W } from "./ArtboardCard";
import { design, live, openDialog, useDesign } from "./store";
import { movePositions } from "./sync";
import type { Artboard, Comment, Pos } from "./types";

const SLOT_H = 400;
const GAP = 40;
const PER_ROW = 3;

function flow(boards: Artboard[], saved: Record<string, Pos>): Record<string, Pos> {
  const out: Record<string, Pos> = {};
  let i = 0;
  for (const a of boards) {
    if (saved[a.id]) out[a.id] = saved[a.id];
    else {
      out[a.id] = { x: 24 + (i % PER_ROW) * (CARD_W + GAP), y: 24 + Math.floor(i / PER_ROW) * SLOT_H };
      i += 1;
    }
  }
  return out;
}

export function ArtboardsDetail() {
  const data = useDesign((s) => s.data);
  const slug = useDesign((s) => s.slug);
  const saved = useDesign((s) => s.positions);
  const view = useDesign((s) => s.view);
  const bust = useDesign((s) => s.bust);
  const sel = useDesign((s) => s.sel);
  const running = useDesign(live);
  const busy = useDesign((s) => s.busy);
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [zoom, setZoom] = useState(1);
  const scroll = useRef<HTMLDivElement>(null);
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const boards = useMemo(() => data?.artboards || [], [data]);
  const placed = useMemo(() => flow(boards, saved), [boards, saved]);
  const pins = useMemo(() => {
    const by = new Map<string, Comment[]>();
    for (const c of data?.comments || []) if (!c.resolved) by.set(c.artboard, [...(by.get(c.artboard) || []), c]);
    return by;
  }, [data]);
  const ext = useMemo(() => {
    const ps = Object.values(placed);
    return { w: Math.max(700, ...ps.map((p) => p.x + CARD_W + 60)), h: Math.max(420, ...ps.map((p) => p.y + SLOT_H + 40)) };
  }, [placed]);

  const onDown = useCallback((ev: PointerEvent<HTMLElement>, id: string) => {
    if (ev.button !== 0 || (ev.target as HTMLElement).closest("button, select, input, a")) return;
    ev.preventDefault();
    ev.stopPropagation();
    design.update((s) => (s.sel === id ? {} : { sel: id }));
    const x0 = ev.clientX, y0 = ev.clientY;
    let last = { id, dx: 0, dy: 0 };
    const move = (m: globalThis.PointerEvent) => {
      last = { id, dx: (m.clientX - x0) / zoomRef.current, dy: (m.clientY - y0) / zoomRef.current };
      setDrag(last);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setDrag(null);
      if (Math.hypot(last.dx, last.dy) < 3) return;
      const s = design.get();
      const at = flow(s.data?.artboards || [], s.positions)[id];
      if (at) movePositions({ [id]: { x: Math.max(0, at.x + last.dx), y: Math.max(0, at.y + last.dy) } });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  const fitted = useRef("");
  useEffect(() => {
    // the first time a project draws: fit it when it is wider or taller than the panel
    const el = scroll.current;
    if (!el || !boards.length || fitted.current === slug) return;
    fitted.current = slug;
    if (ext.w > el.clientWidth || ext.h > el.clientHeight) setZoom(Math.max(0.25, Math.min(1, (el.clientWidth - 24) / ext.w, (el.clientHeight - 24) / ext.h)));
  }, [slug, boards.length, ext.w, ext.h]);
  const fit = () => {
    const el = scroll.current;
    if (el) setZoom(Math.max(0.25, Math.min(1, (el.clientWidth - 24) / ext.w, (el.clientHeight - 24) / ext.h)));
  };
  if (!data) return <Empty title="No project open" body="Pick one in Projects, or make a new one." />;
  return (
    <div className="da">
      <div className="da-bar">
        <span className="mono muted">{boards.length} artboard{boards.length === 1 ? "" : "s"}</span>
        <span className="spacer" />
        <Button size="sm" variant="ghost" onClick={fit} title="Fit every card in the panel">Fit</Button>
        <span className="segmented" role="group" aria-label="Zoom">
          <button onClick={() => setZoom(Math.max(0.25, zoom / 1.2))} aria-label="Zoom out">-</button>
          <button onClick={() => setZoom(1)} title="Back to 100%">{Math.round(zoom * 100)}%</button>
          <button onClick={() => setZoom(Math.min(2, zoom * 1.2))} aria-label="Zoom in">+</button>
        </span>
        <Button size="sm" disabled={!boards.length} onClick={() => openDialog({ kind: "export" })} data-testid="design-export">Export...</Button>
        <Button size="sm" disabled={busy === "handoff"} onClick={() => void handoff()} data-testid="design-handoff">Handoff</Button>
      </div>
      {boards.length ? (
        <div className="da-scroll" ref={scroll}>
          <div style={{ width: ext.w * zoom, height: ext.h * zoom }}>
            <div className="da-world" style={{ width: ext.w, height: ext.h, transform: `scale(${zoom})` }}>
              {boards.map((a) => {
                const p = placed[a.id];
                const d = drag?.id === a.id ? drag : null;
                return (
                  <ArtboardCard key={a.id} a={a} slug={slug} x={p.x + (d?.dx || 0)} y={p.y + (d?.dy || 0)} shown={view[a.id] || 0} bust={bust[a.id] || 0}
                                pins={pins.get(a.id) || NO_PINS} selected={sel === a.id} dragging={!!d} running={running} onDown={onDown} />
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <Empty title="No artboards yet" body="Say what to design in the Thread panel: the first turn makes them." />
      )}
    </div>
  );
}

const NO_PINS: Comment[] = [];

export function ArtboardsGlance() {
  const n = useDesign((s) => s.data?.artboards.length || 0);
  const versions = useDesign((s) => (s.data?.artboards || []).reduce((m, a) => m + a.versions.length, 0));
  const pins = useDesign((s) => (s.data?.comments || []).filter((c) => !c.resolved).length);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={n} label="artboards" />
        <Metric value={versions} label="versions" />
        <Metric value={pins} label="open pins" tone={pins ? "warn" : undefined} />
      </div>
    </div>
  );
}

export function useArtboardsMotion(): MotionState {
  const running = useDesign(live);
  const any = useDesign((s) => !!s.data?.artboards.length);
  return running ? "working" : any ? "idle" : "none";
}
