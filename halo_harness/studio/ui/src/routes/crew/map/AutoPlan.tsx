// Agents -> 3 · Map on Auto (3.6.0.5 A11, A14, A22; the design's M1), drawn by MapMain in place of the drawing, the
// strip and the cards: Auto has no plan to edit -- main picks who works on each task as it goes -- so the tab shows the
// reserved notice row (NoticeRow.tsx: never L1 or L2 here, quietOf.ts), then M1 with its ONE Watch button (the newest
// session on Auto, else "Nothing runs on Auto right now."), then main alone (no dot, no line), then a goal run going
// (LitLine.tsx RunRow, the goal runs read here as MapCanvas reads them). M1's room is reserved from the first draw for
// the longer of its two forms (a hidden twin, as the top line's), so the button coming or going moves nothing.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "../../../lib/ui";
import { autoWatch, m1Head, M1_TAIL, NOTHING_ON_AUTO, WATCH } from "./autoWords";
import { BOX_W } from "./layout";
import { RunRow } from "./LitLine";
import { MapBox } from "./MapBox";
import { useMap } from "./mapStore";
import { useQuiet } from "./mapQuiet";
import { watchLive } from "./mapSwitch";
import type { MapDetail } from "./mapTypes";
import { NoticeRow } from "./NoticeRow";
import { view } from "./view";
import { startOrchestra } from "../../orchestra/sync";
import { UseThis, useNotNext } from "./useThis";

const NONE: never[] = [];

/** The tallest of the twin's forms at this width, measured again only when the words or the width change. */
function useTwinRoom(key: string) {
  const box = useRef<HTMLDivElement>(null), twin = useRef<HTMLDivElement>(null);
  const [h, setH] = useState(0);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(Math.round(el.clientWidth)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useLayoutEffect(() => {
    const kids = [...(twin.current?.children || [])] as HTMLElement[];
    const got = Math.max(0, ...kids.map((k) => k.offsetHeight));
    if (got && Math.abs(got - h) > 0.5) setH(got);
  }, [key, width]); // eslint-disable-line react-hooks/exhaustive-deps
  return { box, twin, h };
}

export function AutoPlan() {
  const detail = useMap((s) => s.detail);
  const names = (detail as (MapDetail & { hand_to?: string[] }) | null)?.hand_to || NONE;
  const sid = autoWatch(useQuiet().on);
  const head = m1Head(names);
  const { box, twin, h } = useTwinRoom(head);
  const not = useNotNext(); // 3.6.0.11 SM: Auto open while new sessions run another map: the line, its room from the first draw
  const nx = useTwinRoom(not.room);
  useEffect(() => startOrchestra(), []); // the goal runs RunRow shows (MapCanvas starts them on every other map)
  const main = view(detail ? { ...detail.map, boxes: [], lines: [] } : null, [], []).boxes[0];
  return (
    <div className="mp-auto" data-testid="map-auto">
      <NoticeRow />
      <div className="mp-topline-room" ref={box} style={h ? { minHeight: h } : undefined}>
        <p className="cw-line mp-topline" data-testid="map-auto-plan">
          {head} {sid ? <Button size="sm" data-testid="map-auto-watch" onClick={() => watchLive(sid)}>{WATCH}</Button> : NOTHING_ON_AUTO} {M1_TAIL}
        </p>
        <div className="mp-notice-twin" ref={twin} aria-hidden="true">
          <p className="cw-line mp-topline">{head} <button type="button" tabIndex={-1} className="btn btn-default btn-sm"><span className="btn-label">{WATCH}</span></button> {M1_TAIL}</p>
          <p className="cw-line mp-topline">{head} {NOTHING_ON_AUTO} {M1_TAIL}</p>
        </div>
      </div>
      <div className="mp-topline-room" ref={nx.box} style={nx.h ? { minHeight: nx.h } : undefined}>
        {not.line && <p className="cw-line mp-topline" data-testid="map-auto-next">{not.line} <UseThis name={not.name} /></p>}
        <div className="mp-notice-twin" ref={nx.twin} aria-hidden="true">
          {not.room && <p className="cw-line mp-topline">{not.room} <UseThis name={not.name} twin /></p>}
        </div>
      </div>
      {main && (
        <div className="mp-auto-main" data-testid="map-auto-main" data-box="main">
          <MapBox b={main} facts={detail?.boxes.main} mainFacts={detail ? { ...detail.main, start: detail.start, auto: true } : undefined} style={{ width: BOX_W }} />
        </div>
      )}
      <RunRow />
    </div>
  );
}
