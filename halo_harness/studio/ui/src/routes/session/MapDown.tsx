// Session's Live drawer: the session's map drawn top to bottom (3.6.0.2 R7 R9 R10 R11 R12), from layoutDown.ts (width in,
// boxes and lines out; R8's routing is its own). The frame is this file's: the head (the truth line, the link, the zoom),
// the scroll box, the boxes as measured, the "↓ {n} more below" slot. Each box's face and the lit data are LitMini.tsx's.
// - R7: the width laid out is the scroll box's clientWidth (`scrollbar-gutter: stable`), re-read on resize: two 184 px boxes
//   a row from 400 px, one under it; main alone on row 0; nothing sideways.
// - R9: it opens at 100 % (fitted with 12 px text the floor is 1.0); a hand zoom goes from 75 % to 200 %.
// - R10: no cap, no ellipsis: a box is estimated (estimateDown), then measured once drawn and it grows to hold its words.
// - R11: at rest no box is cut: the scroll box ends under the last whole row (downFit.ts); a slot at a fixed bottom says how
//   many boxes wait below and scrolls one row a press.
// - R12: while the pointer is on it the drawing keeps its geometry (hold.ts) and text changes in place; after a hand scroll
//   the first box he sees keeps its place; Fit (100 %, top) only on the first draw and on a different map.
import { useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";
import { clampZoom, fitScale, NAV_HELP, useCanvasNav, useZoomPoint } from "../../lib/canvasNav";
import { goSection } from "../../lib/store";
import { ZoomButtons } from "../../lib/ui/ZoomButtons";
import { setAgentsView } from "../agents/store";
import { useHold } from "../crew/map/hold";
import { STATE_WORDS } from "../crew/map/LitBits";
import { LitFace, litState, useLit } from "../crew/map/LitMini";
import type { LitSession } from "../crew/map/litStore";
import { estimateDown, layoutDown, type Down } from "../crew/map/layoutDown";
import { openMap } from "../crew/map/mapStore";
import { moreBelow } from "../crew/map/truth";
import { belowCount, firstSeen, keepSeen, nextTop, rowsOf, viewHeight } from "./downFit";

const NAV_ID = "session-lit-map";
const READ_PX = 12; // R9: the rows' size on screen at 100 %: fitted with it the floor is 1.0, so it always opens at 100 %
const MIN = 0.75, MAX = 2; // a zoom by hand: down to 75 %, never on opening

/** An element's clientWidth / clientHeight, read before the first paint and again on every resize. */
function useSize(ref: RefObject<HTMLElement | null>, on: boolean): { w: number; h: number } {
  const [s, setS] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setS((o) => (o.w === el.clientWidth && o.h === el.clientHeight ? o : { w: el.clientWidth, h: el.clientHeight }));
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [on]); // eslint-disable-line react-hooks/exhaustive-deps
  return s;
}

/** `line`: the truth sentence over the drawing (R2: it depends on the session's map, never on busy). */
export function MapDown({ s, line, state }: { s: LitSession; line: string; state: string }) {
  const { detail, ov, v } = useLit(s);
  const drawn = !!detail;
  const root = useRef<HTMLDivElement>(null), roomEl = useRef<HTMLDivElement>(null);
  const scroll = useRef<HTMLDivElement>(null), world = useRef<HTMLDivElement>(null);
  const cw = useSize(scroll, drawn).w, room = useSize(roomEl, drawn).h;
  const [heights, setHeights] = useState<Record<string, number>>({});
  // the boxes no line reaches wait for R44's heading (a later batch): today, as before, the drawing is the reached map
  const live = useMemo(() => layoutDown({ ...v, strip: [] }, (b) => heights[b.id] ?? estimateDown(b), cw), [v, heights, cw]);
  const { held } = useHold(root);
  const kept = useRef<{ map: string; cw: number; g: Down; ready: boolean } | null>(null);
  let was = kept.current;
  if (!held || !was || !was.ready || was.map !== (s.map || "") || was.cw !== cw) {
    was = kept.current = { map: s.map || "", cw, g: live, ready: live.boxes.every((b) => heights[b.id] != null) };
  }
  const g = was.g; // R12: under the pointer the last geometry stays (once measured); the change is drawn when it leaves

  const [k, setK] = useState(1);
  const [restTop, setRestTop] = useState(0); // the scrollTop the scroll box's height is counted from
  const [top, setTop] = useState(0); // the scrollTop now (what is below)
  const pending = useRef<{ t: number; tries: number } | null>(null);
  const seen = useRef<{ id: string; off: number } | null>(null);
  const settle = useRef(0);
  const rows = useMemo(() => rowsOf(g.boxes), [g]);
  const H = viewHeight(rows, k, restTop, room);
  const go = (t: number) => ((pending.current = { t, tries: 0 }), setRestTop(t));
  const zoomPt = useZoomPoint(scroll, k, setK);
  const fit = () => { // R9 R12: 100 % and the top; past the room it scrolls down (R11), never smaller
    const el = scroll.current;
    if (!el) return;
    setK(fitScale(el.clientWidth, Math.max(1, room), g.w, g.h, { max: 1, textPx: READ_PX, pad: 4 }).zoom);
    seen.current = null;
    el.scrollLeft = 0;
    go(0);
  };
  const nav = useCanvasNav(scroll, { zoom: k, zoomAt: zoomPt, fit, id: NAV_ID, min: MIN, max: MAX, background: ".mp-mini-world, .mp-mini-size, .mp-lines" });
  useLayoutEffect(() => { // R12: fitted on the first draw and on a different map, never on a box arriving
    if (drawn) nav.fit();
  }, [drawn, s.map]); // eslint-disable-line react-hooks/exhaustive-deps
  const last = useRef(g);
  useLayoutEffect(() => { // R12: a new drawing keeps the first box he sees where it was (a hand scroll; the top needs nothing)
    if (last.current === g) return;
    last.current = g;
    const el = scroll.current, t = el && seen.current && el.scrollTop > 0.5 ? keepSeen(g.boxes, k, seen.current) : null;
    if (t != null) go(t);
  }, [g]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { // a scroll that waited for the scroll box's new height is made once it has it
    const el = scroll.current, p = pending.current;
    if (!el || !p) return;
    el.scrollTop = p.t;
    if (Math.abs(el.scrollTop - p.t) <= 1 || ++p.tries > 3) pending.current = null;
  });
  useLayoutEffect(() => { // R10: each box as tall as its words, measured once drawn (as MapCanvas.tsx measures)
    const got: Record<string, number> = {};
    world.current?.querySelectorAll<HTMLElement>("[data-box]").forEach((el) => {
      got[el.dataset.box!] = (el.querySelector<HTMLElement>(".mp-inner")?.offsetHeight || 0) + 20; // its words, padding and border
    });
    if (Object.entries(got).some(([id, h]) => Math.abs((heights[id] || 0) - h) > 1)) setHeights((x) => ({ ...x, ...got }));
  });
  const onScroll = () => {
    const el = scroll.current;
    if (!el) return;
    const t = el.scrollTop;
    setTop(t);
    seen.current = firstSeen(g.boxes, k, t);
    window.clearTimeout(settle.current);
    if (!pending.current) settle.current = window.setTimeout(() => setRestTop(el.scrollTop), 200); // at rest: no box cut below
  };
  const n = belowCount(g.boxes, k, top, H);
  const down = () => {
    const t = scroll.current ? nextTop(rows, k, scroll.current.scrollTop) : null;
    if (t != null) go(t);
  };
  const fitted = !nav.byHand() && Math.abs(k - 1) < 1e-3;
  const open = () => { setAgentsView("map"); goSection("agents", "map"); void openMap(s.map || ""); };
  if (!detail) return <p className="cw-line" data-testid="session-lit-map-reading">Reading the map {s.map}...</p>;
  return (
    <div className="mp-mini mp-down" ref={root} data-testid="session-lit-map" data-dir="down" data-map={s.map || ""} data-sid={s.sid}
         data-held={held ? "1" : undefined}>
      <div className="mp-mini-head mp-down-head">
        <span className="cw-line" data-testid="session-lit-line" data-state={state} data-sid={s.sid}>{line}</span>
        <div className="mp-down-tools">
          <button type="button" className="mp-link" onClick={open} data-testid="session-lit-open">Open it on the Map tab</button>
          <ZoomButtons zoom={k} zoomAt={(z) => nav.zoomAt(clampZoom(z, MIN, MAX))} fit={nav.fit} fitted={fitted} />
        </div>
      </div>
      <div className="mp-down-room" ref={roomEl}>
        <div className="mp-mini-scroll rc-scroll" ref={scroll} style={{ height: H }} onScroll={onScroll} tabIndex={0} data-pan="1"
             title={NAV_HELP} aria-label="The session's map">
          <div className="mp-mini-size" style={{ width: g.w * k, height: g.h * k }}>
            <div className="mp-mini-world" ref={world} data-zoom={k.toFixed(3)} style={{ width: g.w, height: g.h, transform: `scale(${k})` }}>
              <svg className="mp-lines" width={g.w} height={g.h} aria-hidden="true">
                {g.lines.map((l) => <path key={l.key} d={l.d} className="mp-line" data-helper={l.helper || undefined}
                                          data-pulse={ov?.pulses.some((p) => p.from === l.from && p.to === l.to) ? "1" : undefined} />)}
              </svg>
              {g.boxes.map((b) => {
                const { st, helper } = litState(b, ov);
                return (
                  <div key={b.id} className="mp-box" data-lit="live" data-state={st} data-helper={helper} data-kind={b.kind} data-new={b.isNew ? "" : undefined}
                       data-testid="session-lit-box" data-box={b.id} title={`${b.name}: ${STATE_WORDS[st]}`}
                       style={{ position: "absolute", left: b.x, top: b.y, width: b.w, height: b.h }}>
                    <LitFace b={b} ov={ov} />
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      <div className="mp-down-below" data-testid="session-map-below">
        {n > 0 && <button type="button" className="mp-link" data-testid="map-more-below" onClick={down}>{moreBelow(n)}</button>}
      </div>
    </div>
  );
}
