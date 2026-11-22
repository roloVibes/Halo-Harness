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
// - P4 batch 13 (runParts.tsx, as Session's drawer): the tool clock, the talk pulse, "+{n} under it" to the Feed, J / K;
//   the box waited on outlined and the wait link at the left of the tools row, on its reserved row (runWait.tsx WaitRow;
//   P8: its words whole, never cut).
// - 3.6.0.5 B26 B27 (Auto only, the row says map_plain): a slot under the scroll box, its line reserved from the first draw,
//   names a working group wholly below the view and brings its head into view; a group card's Open in Agents -> Live
//   (litStore.ts focus) puts that group's head at the top with its border pulsing 2 s. On a map of his: as before.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { clampZoom, fitScale, NAV_HELP, useCanvasNav, useZoomPoint } from "../../lib/canvasNav";
import { ZoomButtons } from "../../lib/ui/ZoomButtons";
import { useHold } from "../crew/map/hold";
import { BOX_W, LABEL_H, LABEL_W, layout } from "../crew/map/layout";
import { estimateDown, type PlacedDown, type RoutedDown } from "../crew/map/layoutDown";
import { useLit } from "../crew/map/LitMini";
import { setFeedFor, takeFocus, useLitStore, type LitSession } from "../crew/map/litStore";
import { groupId } from "../crew/map/litView";
import { slotWords } from "../crew/map/groupWords";
import { slotAim, useSlotGo, waitAnswer } from "../crew/map/cover";
import { whenWords } from "../crew/map/mapTypes";
import { RunLine } from "../crew/map/RunLine";
import { drawnAll, selected, useHeld, useMeasure, useStepCard } from "../crew/map/runFrame";
import { useAskedBox } from "../crew/map/askBox";
import { StepIn } from "../crew/map/StepIn";
import type { Hit } from "../crew/map/stepInTarget";
import { readingMap, removedAt, type TruthFacts } from "../crew/map/truth";
import { DownBox } from "../session/DownBox";
import { openFeed } from "../crew/map/feedOpen";
import { RunCtx, useRunParts, useShown, useStepKeys, useTalkLines } from "../crew/map/runParts";
import { useRunWait, WaitRow } from "../crew/map/runWait";
import { firstSeen, keepSeen } from "../session/downFit";
import { LiveHead } from "./LiveHead";
import { focusStep, sameAnswer, slotAnswer, type SlotAnswer } from "./liveSlot";

const NAV_ID = "agents-live";
const READ_PX = 12; // the rows' size on screen at 100 %: fitted with it the floor is 1.0, so it opens at 100 %
const MIN = 0.75, MAX = 2;

type G = { boxes: PlacedDown[]; lines: (RoutedDown & { lx: number; ly: number })[]; w: number; h: number };

/** `f`: the session's facts (its row); the head says them, held with the drawing (R12). */
export function LiveRun({ s, f: given }: { s: LitSession; f: TruthFacts }) {
  const map = s.map || "";
  const shown = useShown("live");
  const L = useLit(s, undefined, shown);
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
  const ready = fresh.boxes.every((b) => heights[b.id] != null);
  const g = useHeld<G>(held, map, fresh, drawnAll(fresh.boxes, heights));
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
  const nav = useCanvasNav(scroll, { zoom: k, zoomAt: zoomPt, fit, id: NAV_ID, min: MIN, max: MAX, background: ".mp-world, .mp-world-size, .mp-lines",
    resized: s.auto && shown ? () => onScroll() : undefined }); // b/batch08: the slot's answer follows the view's height (the fit's observer)
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
  const focus = useLitStore((x) => x.focus);
  const pulseOff = useRef<(() => void) | null>(null);
  useLayoutEffect(() => { // B27, after the two above so its scroll wins: the group asked for, its head at the top, pulsing 2 s
    const el = scroll.current, box = focus && focus.sid === s.sid ? g.boxes.find((b) => b.id === groupId(focus.n)) : undefined;
    if (!el || !shown) return; // on screen only
    const full = g === fresh && ready; // b/batch07: taken once its box is placed and measured, else dropped at a full draw
    const step = focusStep(focus, s.sid, !!box && (g !== fresh || ready), full);
    if (step === "drop") takeFocus(s.sid);
    if (step !== "take" || !box) return;
    takeFocus(s.sid);
    el.scrollTop = box.y * k;
    const l = box.x * k, r = (box.x + box.w) * k;
    if (l < el.scrollLeft) el.scrollLeft = l;
    else if (r > el.scrollLeft + el.clientWidth) el.scrollLeft = Math.min(l, r - el.clientWidth);
    const node = world.current?.querySelector<HTMLElement>(`[data-box="${CSS.escape(box.id)}"]`);
    if (node) { // a second press restarts the pulse: one attribute, one end listener (once)
      pulseOff.current?.();
      node.removeAttribute("data-pulse");
      void node.offsetWidth;
      const end = (e: AnimationEvent) => {
        if (e.target !== node || e.animationName !== "mp-group-pulse") return void node.addEventListener("animationend", end, { once: true });
        node.removeAttribute("data-pulse");
        pulseOff.current = null;
      };
      node.addEventListener("animationend", end, { once: true });
      node.setAttribute("data-pulse", "");
      pulseOff.current = () => (node.removeEventListener("animationend", end), node.removeAttribute("data-pulse"));
    }
    setCard(null);
  }, [focus, s.sid, g, shown]); // eslint-disable-line react-hooks/exhaustive-deps
  // B26 (Auto only): the slot's answer, set only when it changes, at most once per animation frame of a scroll burst or a
  // change of the view's size
  const [ans, setAns] = useState<SlotAnswer>(null);
  const told = useRef<SlotAnswer>(null), raf = useRef(0);
  const press = useSlotGo("live", root, card, closeCard, (t) => { if (scroll.current) scroll.current.scrollTop = t; }); // L4 R4
  const answer = () => { // 3.6.0.13 L4: first a group that waits on him out of sight (or under the open card), else B26's
    const el = scroll.current, a = s.auto && el ? (L.groups && waitAnswer("live", world.current, el, L.groups, g.boxes, k, el.scrollTop,
      el.clientHeight)) || slotAnswer(g.boxes, L.groups, k, el.scrollTop, el.clientHeight) : null;
    if (!sameAnswer(told.current, a)) setAns((told.current = a));
  };
  useLayoutEffect(answer, [s.auto, g, k, L.groups, drawn, shown, card]); // eslint-disable-line react-hooks/exhaustive-deps
  const onScroll = () => { if (!raf.current) raf.current = requestAnimationFrame(() => ((raf.current = 0), answer())); };
  useEffect(() => () => { cancelAnimationFrame(raf.current); raf.current = 0; }, [shown]); // the view leaves: no frame waits
  const wb = ans ? g.boxes.find((b) => b.id === groupId(ans.n)) : undefined;
  const wbName = ans ? L.groups?.find((x) => x.n === ans.n)?.name || "" : "";
  useMeasure(world, heights, setHeights, true); // R10 (runFrame.ts): never while the view is hidden
  useAskedBox("live", s.sid, L, world, setCard); // an ask's door: the asking agent's box selected, its card open
  const fitted = !nav.byHand() && Math.abs(k - 1) < 1e-3;
  const gone = got && "removed" in got ? got.removed : 0;
  const pulse = (from: string, to: string) => ov?.pulses.find((p) => p.from === from && p.to === to);
  const wait = useRunWait(s.sid, ov, L.now || 0, shown);
  const parts = useRunParts(L.agents, L.now || 0, (aid) => openFeed(`under:${aid}`), wait, held);
  const talks = useTalkLines(ov, s.sid, L.now || 0, g.lines);
  const steps = useStepKeys(world, true);
  return (
    <>
      <LiveHead f={said.current} sid={s.sid} off={ov?.offCount || 0} />
      <RunCtx.Provider value={parts}>
      <div className="ag-live-frame ag-run" ref={root} data-testid="live-frame" data-held={held ? "1" : undefined} onKeyDown={steps}>
        <div className="ag-run-tools">
          <WaitRow world={world} />
          <ZoomButtons zoom={k} zoomAt={(z) => nav.zoomAt(clampZoom(z, MIN, MAX))} fit={nav.fit} fitted={fitted} />
        </div>
        {!drawn && (gone ? <p className="cw-line" data-testid="live-removed">{removedAt(gone)}</p>
          : !(got && "unreadable" in got) && <p className="cw-line" data-testid="live-reading">{readingMap(map)}</p>)}
        {drawn && (
          <div className="mp-scroll rc-scroll" ref={scroll} tabIndex={0} data-pan="1" title={NAV_HELP} aria-label="The session's map" data-testid="live-scroll"
               onScroll={s.auto ? onScroll : undefined}>
            <div className="mp-world-size" style={{ width: g.w * k, height: g.h * k }}>
              <div className="mp-world" ref={world} data-testid="live-world" data-map={map} data-zoom={k.toFixed(3)}
                   style={{ width: g.w, height: g.h, transform: `scale(${k})` }}>
                <svg className="mp-lines" width={g.w} height={g.h} aria-hidden="true">
                  {g.lines.map((l) => <RunLine key={l.key} l={l} lit={L} onPick={pickLine} talk={talks.get(`${l.from}>${l.to}`)} />)}
                </svg>
                {g.lines.filter((l) => !l.helper && !l.to.startsWith("group:")).map((l) => { const p = pulse(l.from, l.to); return ( // 3.6.0.5: no label into a group (its head names it)
                  <span key={`l${l.key}`} className="mp-label mono" data-testid="live-label" data-from={l.from} data-to={l.to}
                        data-pulse={p ? "1" : undefined} style={{ left: l.lx, top: l.ly, width: LABEL_W, height: LABEL_H }}
                        onClick={(e) => (e.stopPropagation(), pickLine(l, e.currentTarget.textContent || ""))}>
                    {p ? p.task || whenWords(l.when) : whenWords(l.when)}
                  </span>); })}
                {g.boxes.map((b) => <DownBox key={b.id} b={b} L={L} sid={s.sid} lines={g.lines} pick={pickIn(b.id, !!b.block?.under)} live sel={selected(card, b.id, b.block?.workflow, b.group?.members)} card={card?.id} />)}
              </div>
            </div>
          </div>
        )}
        {s.auto && <div className="ag-live-below" data-testid="live-below">
          {ans && wb && <button type="button" className="mp-link" data-testid="live-more-below" data-group={ans.n}
                         data-wait={ans.arrow ? "" : undefined} data-arrow={ans.arrow || "down"} onClick={() => press(ans.arrow,
                           ans.arrow === "under" || !scroll.current ? null : slotAim(world.current, scroll.current, ans, wb.y * k, scroll.current.clientHeight))}>
            {slotWords(wbName, ans.arrow, ans.more)}</button>}
        </div>}
        {card && <StepIn t={card} map={map} sid={s.sid} close={closeCard} onLive={closeCard} />}
      </div>
      </RunCtx.Provider>
    </>
  );
}
