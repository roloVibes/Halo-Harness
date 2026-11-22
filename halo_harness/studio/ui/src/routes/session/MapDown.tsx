// Session's Live drawer: the session's map drawn top to bottom (3.6.0.2 R7 R9 R10 R11 R12), from layoutDown.ts (width in,
// boxes and lines out; R8's routing is its own). The frame is this file's: the head (the truth block, TruthBlock.tsx; the link, the zoom),
// the scroll box, the boxes as measured, the "↓ {n} more below" slot. Each box's face and the lit data are LitMini.tsx's.
// - R7: the width laid out is the scroll box's clientWidth (`scrollbar-gutter: stable`), re-read on resize: two 184 px boxes
//   a row from 400 px, one under it; main alone on row 0; nothing sideways.
// - R9: it opens at 100 % (fitted with 12 px text the floor is 1.0); a hand zoom goes from 75 % to 200 %.
// - R10: no cap, no ellipsis: a box is estimated (estimateDown), then measured once drawn and it grows to hold its words.
// - R11: at rest no box is cut: the scroll box ends under the last whole row (downFit.ts); a slot at a fixed bottom says how
//   many boxes wait below and scrolls one row a press. r/batch04: on Auto the scroll box is the whole room from the first
//   draw (a group cut at its foot is reached by the scroll; the slot names a working one).
// - R12: while the pointer is on it or a card is open the drawing keeps its geometry (hold.ts) and text changes in place;
//   after a hand scroll the first box he sees keeps its place; Fit (100 %, top) only on the first draw and on a different map.
// - R18: a click on a box, a step row or a line opens the step-in card (crew/map/StepIn.tsx) 6 px under its box (O1-3),
//   for the agent the session's rows name at that moment (stepInTarget.ts); R43: a box's hover (DownBox.tsx).
// - R28: nothing waits on the network: the head (truth block, status line, the pair) is drawn from the row first; the map
//   is read after it, softly, by version (mapFiles.ts); a map gone says "This map was removed at {t}.".
// - R29-R31: the pair Running | Just built (two maps only) and the head (BuiltBar.tsx), at the top of the drawing's own
//   box: no room until a build lands, then the drawing moves down once and no control moves; Just built is drawn calm
//   (no overlay); the boxes a build in this session wrote carry "new {t}" (built.ts tagOf).
// - P4 batch 13 (crew/map/runParts.tsx, as Agents -> Live): the tool clock, the talk pulse, "+{n} under it" (the Feed is
//   Agents -> Live's: it opens there on this session), J / K; its clock only while Session is on screen; the box waited
//   on outlined and the wait link in the bottom slot, on its own reserved lines beside "more below" (runWait.tsx WaitRow; P8:
//   its words whole, never cut).
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";
import { clampZoom, fitScale, NAV_HELP, useCanvasNav, useZoomPoint } from "../../lib/canvasNav";
import { ZoomButtons } from "../../lib/ui/ZoomButtons";
import { holding, tagOf, useBuilt } from "../crew/map/built";
import { useHold } from "../crew/map/hold";
import { useLit } from "../crew/map/LitMini";
import { RunLine } from "../crew/map/RunLine";
import { drawnAll, selected, useHeld, useMeasure, useStepCard } from "../crew/map/runFrame";
import { useAskedBox } from "../crew/map/askBox";
import { useRings } from "../crew/map/useRings";
import { BELOW_SAMPLE, slotWords } from "../crew/map/groupWords";
import { slotAim, useSlotGo, waitAnswer } from "../crew/map/cover";
import { groupId } from "../crew/map/litView";
import { sameAnswer, type SlotAnswer } from "../agents/liveSlot";
import { StepIn } from "../crew/map/StepIn";
import { openFeed } from "../crew/map/feedOpen";
import { RunCtx, useRunParts, useShown, useStepKeys, useTalkLines } from "../crew/map/runParts";
import { useRunWait, WaitRow } from "../crew/map/runWait";
import type { LitSession } from "../crew/map/litStore";
import { estimateDown, layoutDown, type Down } from "../crew/map/layoutDown";
import { moreBelow, openInAgents, readingMap, removedAt, type TruthFacts } from "../crew/map/truth";
import { BuiltBar } from "./BuiltBar";
import { belowCount, drawingHeight, firstSeen, keepSeen, nextTop, rowsOf, scrollSize, slotOf } from "./downFit";
import { DownBox } from "./DownBox";
import { openInLive } from "./store";
import { TruthBlock } from "./TruthBlock";

const NAV_ID = "session-lit-map";
const READ_PX = 12; // R9: the rows' size on screen at 100 %: fitted with it the floor is 1.0, so it always opens at 100 %
const MIN = 0.75, MAX = 2; // a zoom by hand: down to 75 %, never on opening
// b/batch07, b/batch08: on Auto the slot's room is, from the first draw, a hidden twin of its words for a long name of
// ordinary letters (BELOW_SAMPLE, 60 characters) with a two-digit count; a name of wider letters may add a line, never cut
// ordinary letters with a two-digit count; 3.6.0.13 L4: the slot's longest form (the under form)
const BELOW_ROOM = slotWords(BELOW_SAMPLE, "under", 99);

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

/** `f`: the session's facts for the truth block over the drawing (R2, R20: its map, never busy). */
export function MapDown({ s, f: given }: { s: LitSession; f: TruthFacts }) {
  const which = useBuilt((x) => x.which[s.sid]);
  const just = useBuilt((x) => x.last[s.sid]);
  const tags = useBuilt((x) => x.tags), flows = useBuilt((x) => x.flows);
  const own = s.map || "";
  const shown = which === "built" && just?.kind === "other" && just.map ? just.map : own; // R30: Just built, or Running
  const on = useShown("session");
  const L = useLit(s, shown !== own ? { map: shown, unlit: true } : undefined, on);
  const { detail, ov, v, got } = L;
  const f = got && "unreadable" in got && shown === own ? { ...given, unreadable: s.path || own } : given; // R50: T12
  const drawn = !!detail;
  const root = useRef<HTMLDivElement>(null), roomEl = useRef<HTMLDivElement>(null);
  const scroll = useRef<HTMLDivElement>(null), world = useRef<HTMLDivElement>(null);
  const cw = useSize(scroll, drawn).w, room = useSize(roomEl, drawn).h;
  const [heights, setHeights] = useState<Record<string, number>>({});
  // the boxes no line reaches wait for R44's heading (a later batch): today, as before, the drawing is the reached map
  const live = useMemo(() => layoutDown({ ...v, strip: [] }, (b) => heights[b.id] ?? estimateDown(b), cw), [v, heights, cw]);
  const { card, setCard, pick, pickLine, closeCard, open } = useStepCard(L, "session"); // R18 (runFrame.ts)
  const { held } = useHold(root, !!card);
  useEffect(() => holding(s.sid, held), [s.sid, held]); // R30: Just built is chosen only while this is not held
  useEffect(() => () => holding(s.sid, false), [s.sid]);
  useEffect(() => setCard(null), [s.sid, shown]);
  // R12: under the pointer the last geometry stays (once measured); the change is drawn when it leaves
  const g = useHeld<Down>(held, `${shown}|${cw}`, live, drawnAll(live.boxes, heights));

  const [k, setK] = useState(1);
  const [restTop, setRestTop] = useState(0); // the scrollTop the scroll box's height is counted from
  const [top, setTop] = useState(0); // the scrollTop now (what is below)
  const pending = useRef<{ t: number; tries: number } | null>(null);
  const seen = useRef<{ id: string; off: number } | null>(null);
  const settle = useRef(0);
  useEffect(() => () => window.clearTimeout(settle.current), []); // the hand scroll's settle never fires once it is gone
  const rows = useMemo(() => rowsOf(g.boxes), [g]);
  // r/batch04: on Auto (the groups' own test, LitMini.tsx: the row says so and its own map is shown) the whole room; else R11
  const onAuto = !!s.auto && shown === own;
  const H = drawingHeight(onAuto, rows, k, restTop, room);
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
  }, [drawn, shown]); // eslint-disable-line react-hooks/exhaustive-deps
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
  useMeasure(world, heights, setHeights); // R10 (runFrame.ts)
  useRings("session", world, scroll, g, L.groups, L.now || 0, on); // 3.6.0.13 L5 L6: a box rings once when something happens to it
  useAskedBox("session", s.sid, L, world, setCard); // an ask's door: the asking agent's box selected, its card open
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
  // 3.6.0.13 L4 on Auto: first a group that waits on him out of sight (or under the open card), else B26's working group
  // not wholly in view below (r/batch04); set only when it changes; a press with the card open folds it first (R4)
  const press = useSlotGo("session", root, card, closeCard, go);
  const [ans, setAns] = useState<SlotAnswer>(null);
  useLayoutEffect(() => {
    const el = scroll.current, gs = L.groups, sl = gs && el ? waitAnswer("session", world.current, el, gs, g.boxes, k, top, H) || slotOf(g.boxes, gs, k, top, H) : null;
    const a = sl && "box" in sl ? { n: sl.box.group!.n, more: sl.more } : sl;
    setAns((o) => (sameAnswer(o, a) ? o : a));
  }, [g, top, k, L.groups, card, open, H]); // eslint-disable-line react-hooks/exhaustive-deps
  const wb = ans ? g.boxes.find((b) => b.id === groupId(ans.n)) : undefined;
  const wbName = ans ? L.groups?.find((x) => x.n === ans.n)?.name || "" : "";
  const slot = () => ans && wb && scroll.current && press(ans.arrow, ans.arrow === "under" ? null : slotAim(world.current, scroll.current, ans, wb.y * k, H));
  const fitted = !nav.byHand() && Math.abs(k - 1) < 1e-3;
  const gone = got && "removed" in got ? got.removed : 0;
  const wait = useRunWait(s.sid, L.unlit ? null : ov, L.now || 0, on);
  const parts = useRunParts(L.agents, L.now || 0, (aid) => (openInLive(s.sid), openFeed(`under:${aid}`)), wait, held);
  const talks = useTalkLines(ov, s.sid, L.now || 0, g.lines);
  const steps = useStepKeys(world, false);
  return ( // R28: the head first, from the row; the drawing once its map is read (`session-lit-map` only then)
    <div className="mp-mini mp-down" ref={root} data-testid={drawn ? "session-lit-map" : "session-lit-map-wait"} data-dir="down" data-map={shown}
         data-sid={s.sid} data-held={held ? "1" : undefined} onKeyDown={steps}>
      <RunCtx.Provider value={parts}>
      <div className="mp-mini-head mp-down-head">
        <TruthBlock f={f} sid={s.sid} where={s} off={L.unlit ? 0 : ov?.offCount || 0} />
        <div className="mp-down-tools">
          <button type="button" className="mp-link" onClick={() => openInLive(s.sid)} data-testid="session-lit-open">{openInAgents().label}</button>
          <ZoomButtons zoom={k} zoomAt={(z) => nav.zoomAt(clampZoom(z, MIN, MAX))} fit={nav.fit} fitted={fitted} />
        </div>
      </div>
      <div className="mp-down-room">
        <BuiltBar s={s} />
        <div className="mp-down-fill" ref={roomEl}>
        {!drawn && (gone ? <p className="cw-line" data-testid="session-map-removed">{removedAt(gone)}</p>
          : !(got && "unreadable" in got) && <p className="cw-line" data-testid="session-lit-map-reading">{readingMap(shown)}</p>)}
        {drawn && <div className="mp-mini-scroll rc-scroll" ref={scroll} style={{ height: H }} onScroll={onScroll} tabIndex={0} data-pan="1"
             title={NAV_HELP} aria-label="The session's map">
          <div className="mp-mini-size" style={{ width: g.w * k, height: scrollSize(onAuto, g.boxes, k, g.h, H) }}>
            <div className="mp-mini-world" ref={world} data-zoom={k.toFixed(3)} style={{ width: g.w, height: g.h, transform: `scale(${k})` }}>
              <svg className="mp-lines" width={g.w} height={g.h} aria-hidden="true">
                {g.lines.map((l) => <RunLine key={l.key} l={l} lit={L} onPick={pickLine} talk={talks.get(`${l.from}>${l.to}`)} />)}
              </svg>
              {g.boxes.map((b) => <DownBox key={b.id} b={b} L={L} sid={s.sid} lines={g.lines} pick={pick} built={tagOf({ tags, flows }, s.sid, shown, b)} sel={selected(card, b.id, b.block?.workflow, b.group?.members)} card={card?.id} />)}
            </div>
          </div>
        </div>}
        </div>
      </div>
      {card && <StepIn key={card.id} t={card} where="session" map={shown} sid={s.sid} close={closeCard} onLive={() => openInLive(s.sid)} told={s.told} groups={L.groups} />}
      <div className="mp-down-below" data-testid="session-map-below" data-auto={s.auto ? "" : undefined}>
        <div className="mp-down-more">{(n > 0 || !!(ans && wb)) && <button type="button" className="mp-link" data-testid="map-more-below" data-group={wb?.group?.n}
          data-wait={ans?.arrow ? "" : undefined} data-arrow={ans && wb ? ans.arrow || "down" : undefined}
          onClick={ans && wb ? slot : down}>{ans && wb ? slotWords(wbName, ans.arrow, ans.more) : moreBelow(n)}</button>}
          {s.auto && <button type="button" className="mp-link mp-below-twin" tabIndex={-1} aria-hidden="true">{BELOW_ROOM}</button>}</div>
        <WaitRow world={world} />
      </div>
      </RunCtx.Provider>
    </div>
  );
}
