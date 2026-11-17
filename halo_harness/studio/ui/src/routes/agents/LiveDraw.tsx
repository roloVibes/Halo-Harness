// Agents -> 4 · Live's drawing (3.6.0.2 R34): the map the chosen session really follows, laid out left to right as the
// Map lays it out (layout.ts `layout()`: main at the left, a column per step of the longest chain, each line's When in the
// label lane) and lit by what runs, with the run's own parts that Session's Live drawer uses (imported, never copied):
// the session's map read once by version and softly by its scope and path (LitMini.tsx useLit, mapFiles.ts; R50), a
// box's face and its children as named rows, a workflow as its block of steps (DownBox.tsx, LitFace, RunRows.tsx; R14
// R15), every hand-off lighting its line and leaving a trace, work outside the lines dashed in its own colour (RunLine.tsx;
// R16 R17), a click on a box, a step row, a line or its label opening the step-in card (StepIn.tsx; R18).
// Read-only: no connect dot, no When card, no drag, no strip: a label is words, never a button. Never amber: the map
// drawn is the session's, whatever map 3 · Map has open.
// - R12: while the pointer is on the frame or a card is open, the last laid-out geometry stays (hold.ts) and words change in
//   place; the change that moves a box is drawn when the pointer leaves; after a hand scroll the first box he sees keeps
//   its place. Fit (100 %, from the top left) only on the first draw and on a different map; a hand zoom 75 % to 200 %.
// - R49: the layout is computed again only when the map or the overlay's shape (LitMini `v`) or a measured height changes.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { clampZoom, fitScale, NAV_HELP, useCanvasNav, useZoomPoint } from "../../lib/canvasNav";
import { ZoomButtons } from "../../lib/ui/ZoomButtons";
import { useHold } from "../crew/map/hold";
import { BOX_W, LABEL_H, LABEL_W, layout } from "../crew/map/layout";
import { estimateDown, type PlacedDown, type RoutedDown } from "../crew/map/layoutDown";
import { useLit } from "../crew/map/LitMini";
import { setFeedFor, type LitSession } from "../crew/map/litStore";
import { whenWords } from "../crew/map/mapTypes";
import { RunLine } from "../crew/map/RunLine";
import { useHeld, useMeasure, useStepCard } from "../crew/map/runFrame";
import { StepIn } from "../crew/map/StepIn";
import type { Hit } from "../crew/map/stepInTarget";
import { readingMap, removedAt, type TruthFacts } from "../crew/map/truth";
import { DownBox } from "../session/DownBox";
import { firstSeen, keepSeen } from "../session/downFit";
import { LiveHead } from "./LiveHead";

const NAV_ID = "agents-live";
const READ_PX = 12; // the rows' size on screen at 100 %: fitted with it the floor is 1.0, so it opens at 100 %
const MIN = 0.75, MAX = 2;

type G = { boxes: PlacedDown[]; lines: (RoutedDown & { lx: number; ly: number })[]; w: number; h: number };

/** `f`: the session's facts (its row); the head says them, held with the drawing (R12). */
export function LiveRun({ s, f: given }: { s: LitSession; f: TruthFacts }) {
  const map = s.map || "";
  const L = useLit(s);
  const { detail, ov, v, got } = L;
  const f = got && "unreadable" in got ? { ...given, unreadable: s.path || map } : given; // R50: T12
  const drawn = !!detail;
  const root = useRef<HTMLDivElement>(null), scroll = useRef<HTMLDivElement>(null), world = useRef<HTMLDivElement>(null);
  const { card, setCard, pick: pickCard, pickLine, closeCard } = useStepCard(L); // R18 (runFrame.ts, as Session's drawer)
  // R57: a click on a box (its face, a block's head or step) also sets the Feed to that box; the Feed opens only by his hand
  const pickIn = (id: string, loose: boolean) => (h: Hit) => ((loose ? undefined : setFeedFor(id)), pickCard(h));
  const { held } = useHold(root, !!card);
  const said = useRef(f);
  if (!held) said.current = f; // the head's words: a fact that would grow it waits with the drawing
  const [heights, setHeights] = useState<Record<string, number>>({});
  const fresh = useMemo<G>(() => {
    const g = layout(v.boxes, v.lines, (b) => heights[b.id] ?? estimateDown(b));
    return { boxes: g.boxes.map((b) => ({ ...b, w: BOX_W, rank: b.col, row: 0 })), lines: g.lines.map((l) => ({ ...l, entry: 0 })), w: g.w, h: g.h };
  }, [v, heights]);
  // R12: under the pointer the last geometry stays (once measured); the change is drawn when it leaves
  const g = useHeld<G>(held, map, fresh, fresh.boxes.every((b) => heights[b.id] != null));
  useEffect(() => setCard(null), [s.sid, map]);

  const [k, setK] = useState(1);
  const zoomPt = useZoomPoint(scroll, k, setK);
  const fit = () => { // R12: 100 % from the top left; a map wider than the frame scrolls
    const el = scroll.current;
    if (!el) return;
    setK(fitScale(el.clientWidth, el.clientHeight, g.w, g.h, { max: 1, textPx: READ_PX, pad: 16 }).zoom);
    el.scrollLeft = 0;
    el.scrollTop = 0;
  };
  const nav = useCanvasNav(scroll, { zoom: k, zoomAt: zoomPt, fit, id: NAV_ID, min: MIN, max: MAX, background: ".mp-world, .mp-world-size, .mp-lines" });
  useLayoutEffect(() => { // R12: fitted on the first draw and on a different map, never on a box arriving
    if (drawn) nav.fit();
  }, [drawn, map]); // eslint-disable-line react-hooks/exhaustive-deps
  const last = useRef(g);
  useLayoutEffect(() => { // R12: after a hand scroll, a new drawing keeps the first box he sees where it was
    const old = last.current, el = scroll.current;
    last.current = g;
    if (old === g || !el || el.scrollTop < 0.5) return;
    const seen = firstSeen(old.boxes, k, el.scrollTop), t = seen && keepSeen(g.boxes, k, seen); // as Session's drawer (downFit.ts)
    if (t != null && Math.abs(t - el.scrollTop) > 0.5) el.scrollTop = t;
  }, [g]); // eslint-disable-line react-hooks/exhaustive-deps
  useMeasure(world, heights, setHeights, true); // R10 (runFrame.ts): never while the view is hidden
  const fitted = !nav.byHand() && Math.abs(k - 1) < 1e-3;
  const gone = got && "removed" in got ? got.removed : 0;
  const pulse = (from: string, to: string) => ov?.pulses.find((p) => p.from === from && p.to === to);
  return (
    <>
      <LiveHead f={said.current} sid={s.sid} off={ov?.offCount || 0} />
      <div className="ag-live-frame ag-run" ref={root} data-testid="live-frame" data-held={held ? "1" : undefined}>
        <div className="ag-run-tools">
          <ZoomButtons zoom={k} zoomAt={(z) => nav.zoomAt(clampZoom(z, MIN, MAX))} fit={nav.fit} fitted={fitted} />
        </div>
        {!drawn && (gone ? <p className="cw-line" data-testid="live-removed">{removedAt(gone)}</p>
          : !(got && "unreadable" in got) && <p className="cw-line" data-testid="live-reading">{readingMap(map)}</p>)}
        {drawn && (
          <div className="mp-scroll rc-scroll" ref={scroll} tabIndex={0} data-pan="1" title={NAV_HELP} aria-label="The session's map" data-testid="live-scroll">
            <div className="mp-world-size" style={{ width: g.w * k, height: g.h * k }}>
              <div className="mp-world" ref={world} data-testid="live-world" data-map={map} data-zoom={k.toFixed(3)}
                   style={{ width: g.w, height: g.h, transform: `scale(${k})` }}>
                <svg className="mp-lines" width={g.w} height={g.h} aria-hidden="true">
                  {g.lines.map((l) => <RunLine key={l.key} l={l} lit={L} onPick={pickLine} />)}
                </svg>
                {g.lines.filter((l) => !l.helper).map((l) => { const p = pulse(l.from, l.to); return (
                  <span key={`l${l.key}`} className="mp-label mono" data-testid="live-label" data-from={l.from} data-to={l.to}
                        data-pulse={p ? "1" : undefined} style={{ left: l.lx, top: l.ly, width: LABEL_W, height: LABEL_H }}
                        onClick={(e) => (e.stopPropagation(), pickLine(l, e.currentTarget.textContent || ""))}>
                    {p ? p.task || whenWords(l.when) : whenWords(l.when)}
                  </span>); })}
                {g.boxes.map((b) => <DownBox key={b.id} b={b} L={L} sid={s.sid} lines={g.lines} pick={pickIn(b.id, !!b.block?.under)} live />)}
              </div>
            </div>
          </div>
        )}
        {card && <StepIn t={card} map={map} close={closeCard} onLive={closeCard} />}
      </div>
    </>
  );
}
