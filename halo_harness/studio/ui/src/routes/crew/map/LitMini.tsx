// Session's Map panel, lit (3.6.0.0 R4, the brief's point 11): the same lit map as Agents -> 3 · Map, compact and
// read-only -- the map the running session started with, its boxes and lines laid out as on the tab (layout.ts), each
// box's state and what it does now from the same overlay (overlay.ts), the helpers it made up beside their box -- with
// a link to the Map tab. No dot, no label card, nothing to drag. 3.6.0.0 R5 (the old tree went): a session that did not
// start on a map (a bare one, `--agent`) is drawn as main and the helpers it started, with no lines; it zooms and pans
// the house way (lib/canvasNav.ts: Ctrl / Cmd + wheel, a pinch, - % + Fit), fitted to its box until zoomed by hand.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { fitScale, NAV_HELP, recallZoom, useCanvasNav, useZoomPoint } from "../../../lib/canvasNav";
import { ZoomButtons } from "../../../lib/ui/ZoomButtons";
import { api } from "../../../lib/api";
import { useStore } from "../../../lib/store";
import { useSessionRecord } from "../../../lib/work/record";
import { setAgentsView } from "../../agents/store";
import { goSection } from "../../../lib/store";
import { useNow } from "../../fleet/store";
import { STATE_WORDS } from "./LitBits";
import { lit, startLit, type LitSession } from "./litStore";
import { withLit } from "./litView";
import { BOX_W, estimate, layout } from "./layout";
import { openMap } from "./mapStore";
import type { MapDetail } from "./mapTypes";
import { overlay, type OvRow } from "./overlay";
import { view } from "./view";

const files = new Map<string, MapDetail>();
const NAV_ID = "session-lit-map";
const FIT_TEXT = 16; // 12 px on screen at 75 %: the Map's floor
const NO_MAP = { map: { format: "map/1", name: "", boxes: [], lines: [] }, scope: "starter", writable: false, in_use: false,
  problems: [], boxes: {}, main: { agent: "main" } } as unknown as MapDetail;

export function LitMini({ s }: { s: LitSession }) {
  useEffect(() => startLit(), []);
  const [detail, setDetail] = useState<MapDetail | null>(() => (s.map ? files.get(s.map) || null : NO_MAP));
  useEffect(() => {
    if (!s.map) return setDetail(NO_MAP);
    void api.get<MapDetail>(`crew/map/${s.map}`).then((d) => (files.set(s.map!, d), setDetail(d))).catch(() => setDetail(null));
  }, [s.map]);
  const rec = useSessionRecord(s.sid);
  const events = useStore(lit, (x) => x.events[s.sid]);
  const now = useNow(true, 1000) / 1000;
  const ov = useMemo(() => (detail ? overlay(detail.map, (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }) as OvRow), events || [], now) : null),
    [detail, rec, events, now]);
  const v = useMemo(() => withLit(view(detail?.map || null, [], []), ov), [detail, ov]);
  const g = layout(v.boxes, v.lines, (b) => estimate(b, false, 0) + 20);
  const scroll = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(() => recallZoom(NAV_ID) ?? 1);
  const [floor, setFloor] = useState(false); // the last fit stopped at the readable floor
  const zoomPt = useZoomPoint(scroll, k, setK);
  const fit = () => { // fitted to the panel, never under the readable size (the Map's 75 %): past that it pans
    const el = scroll.current;
    if (!el || !g.w) return;
    const f = fitScale(el.clientWidth, el.clientHeight, g.w, g.h, { max: 1, textPx: FIT_TEXT, pad: 4 });
    setK(f.zoom);
    setFloor(f.more);
    el.scrollLeft = 0;
  };
  const nav = useCanvasNav(scroll, { zoom: k, zoomAt: zoomPt, fit, id: NAV_ID, min: 0.5, max: 2, background: ".mp-mini-world, .mp-mini-size, .mp-lines" });
  const drawn = !!detail;
  const n = g.boxes.length;
  useLayoutEffect(() => { // the first drawing, and a box more (a helper), fit their box unless zoomed by hand
    if (drawn && !nav.byHand()) fit();
  }, [drawn, n]); // eslint-disable-line react-hooks/exhaustive-deps
  const el = scroll.current; // past the readable floor the drawing pans: say so, as the Map does (MapCanvas.tsx)
  const more = drawn && (floor || (!!el && (g.w * k > el.clientWidth + 2 || g.h * k > el.clientHeight + 2)));
  const open = () => { setAgentsView("map"); goSection("agents", "map"); void openMap(s.map || ""); };
  if (!detail) return <p className="cw-line" data-testid="session-lit-map-reading">Reading the map {s.map}...</p>;
  return (
    <div className="mp-mini" data-testid="session-lit-map" data-map={s.map || ""} data-sid={s.sid}>
      <div className="mp-mini-head">
        <span className="cw-line">{s.map ? `A session is running on the map ${s.map}.` : "A session is running, not on a map: main and the helpers it started."}</span>
        <button type="button" className="mp-link" onClick={open} data-testid="session-lit-open">Open it on the Map tab</button>
        <ZoomButtons zoom={k} zoomAt={nav.zoomAt} fit={nav.fit} />
      </div>
      {more && <span className="cw-line mp-more" data-testid="map-more" title={NAV_HELP}>more than fits at a readable size: scroll or drag the background, or Ctrl + wheel to zoom</span>}
      <div className="mp-mini-scroll rc-scroll" ref={scroll} tabIndex={0} data-pan="1" title={NAV_HELP} aria-label="The session's map">
        <div className="mp-mini-size" style={{ width: g.w * k, height: g.h * k }}>
        <div className="mp-mini-world" data-zoom={k.toFixed(3)} style={{ width: g.w, height: g.h, transform: `scale(${k})` }}>
          <svg className="mp-lines" width={g.w} height={g.h} aria-hidden="true">
            {g.lines.map((l) => <path key={l.key} d={l.d} className="mp-line" data-helper={l.helper || undefined}
                                      data-pulse={ov?.pulses.some((p) => p.from === l.from && p.to === l.to) ? "1" : undefined} />)}
          </svg>
          {g.boxes.map((b) => {
            const h = b.helper ? ov?.helpers.find((x) => x.aid === b.helper) : undefined;
            const st = h?.state || ov?.boxes[b.id]?.state || "idle";
            return (
              <div key={b.id} className="mp-box" data-lit="live" data-state={st} data-helper={h ? h.aid : undefined} data-testid="session-lit-box" data-box={b.id}
                   style={{ position: "absolute", left: b.x, top: b.y, width: BOX_W, minHeight: b.h }} title={`${b.name}: ${STATE_WORDS[st]}`}>
                <span className="mp-kind mono">{b.main ? "main" : h ? "helper" : b.kind}</span>
                <b className="mp-name">{b.name}</b>
                <span className="mp-lit-row mono" data-state={st}>{STATE_WORDS[st]}{!h && ov?.boxes[b.id] && st === "working" ? ` · ${ov.boxes[b.id].doing}` : ""}</span>
                {h && <span className="mp-tag mp-made">made up for this task</span>}
              </div>
            );
          })}
        </div>
        </div>
      </div>
    </div>
  );
}
