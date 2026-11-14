// The map, drawn (3.6.0.0 R3, the design's "3. Map"): main at the left, a box per agent or workflow, one kind of line
// ("hands work to") with its When in words in the label lane between the columns, never over a box (layout.ts).
// Hovering a box lifts its lines and dims the rest; a line's label opens its When card (or, locked, only says it).
// Zoom the house way (lib/canvasNav.ts: Ctrl / Cmd + wheel, pinch, - % + Fit, 0, a double-click); R8: when the box
// changes width it fits again unless you zoomed it by hand (a hand zoom survives the Add drawer); Fit never goes under
// 75 % -- past that the map pans, from main (top left).
import { useLayoutEffect, useRef, useState } from "react";
import { fitScale, NAV_HELP, recallZoom, useCanvasNav, useZoomPoint } from "../../../lib/canvasNav";
import { ZoomButtons } from "../../../lib/ui/ZoomButtons";
import { useBuilder } from "../builderStore";
import { BOX_W, estimate, LABEL_H, LABEL_W, layout } from "./layout";
import { TopLine } from "./MapBar";
import { MapBox } from "./MapBox";
import { openWhen, useMap } from "./mapStore";
import { whenWords } from "./mapTypes";
import { view } from "./view";
import { litFile, withCard, withLit } from "./litView";
import { lineKey } from "./overlay";
import { useLitNow } from "./useLit";

const FIT_TEXT = 16; // 12 px on screen at 75 %: the Map's floor (the brief: Fit never under 75 %)
const ID = "crew-map";

export function useMapView() {
  const file = useMap((s) => s.detail?.map || null);
  const shown = useMap((s) => s.name);
  const made = useMap((s) => s.made);
  const pending = useBuilder((s) => s.pending, "map");
  const L = useLitNow(); // R4: lit -- helpers beside their box, a parked card's ghosts; no map: main and its helpers only
  const bare = L.nomap || (L.mode === "replay" && L.map !== shown);
  return withLit(view(litFile(file, bare), withCard(pending, L.card), made), L.ov);
}

export function MapCanvas() {
  const v = useMapView();
  const L = useLitNow();
  const detail = useMap((s) => s.detail);
  const open = useMap((s) => s.open);
  const hover = useMap((s) => s.hover);
  const locked = useMap((s) => s.locked);
  const scroll = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const [heights, setHeights] = useState<Record<string, number>>({});
  const [zoom, setZoom] = useState(() => recallZoom(ID) ?? 1);
  const g = layout(v.boxes, v.lines, (b) => heights[b.id] || estimate(b, !!open[b.id], detail?.boxes[b.id]?.facts[0]?.steps?.length || 0));
  const at = useZoomPoint(scroll, zoom, setZoom);
  const fit = () => {
    const el = scroll.current;
    if (!el) return;
    setZoom(fitScale(el.clientWidth, el.clientHeight, g.w, g.h, { max: 1, textPx: FIT_TEXT, pad: 16 }).zoom);
    el.scrollLeft = 0; // past the floor it pans from main, at the top left
    el.scrollTop = 0;
  };
  const nav = useCanvasNav(scroll, { zoom, zoomAt: at, fit, id: ID, min: 0.5, max: 2, background: ".mp-world, .mp-world-size, .mp-lines" });
  const drawn = !!detail;
  useLayoutEffect(() => { // the first drawing fits its box (later: R8, when the box changes width)
    if (drawn && !nav.byHand()) fit();
  }, [drawn, detail?.map.name]); // eslint-disable-line react-hooks/exhaustive-deps
  const helpers = v.boxes.filter((b) => b.helper).length;
  useLayoutEffect(() => { // R4: a made-up helper arriving follows the re-fit rule: never under a zoom made by hand
    if (drawn && helpers && !nav.byHand()) fit();
  }, [helpers]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { // boxes never squish: each is as tall as its text, measured once drawn
    const got: Record<string, number> = {};
    world.current?.querySelectorAll<HTMLElement>("[data-map-box]").forEach((el) => {
      got[el.dataset.mapBox!] = (el.querySelector<HTMLElement>(".mp-inner")?.offsetHeight || 0) + 20; // its text, its padding and border
    });
    if (Object.entries(got).some(([k, h]) => Math.abs((heights[k] || 0) - h) > 1)) setHeights((s) => ({ ...s, ...got }));
  });
  const el = scroll.current;
  const more = drawn && !!el && (g.w * zoom > el.clientWidth + 2 || g.h * zoom > el.clientHeight + 2);
  const lit = (from: string, to: string) => (hover ? (hover === from || hover === to ? "hot" : "dim") : "");
  const pulse = (from: string, to: string) => L.ov?.pulses.find((p) => p.from === from && p.to === to);
  const fired = (from: string, to: string) => L.ov?.lines[lineKey(from, to)];
  const words = (from: string, to: string, when: Parameters<typeof whenWords>[0]) => {
    const p = pulse(from, to), f = fired(from, to);
    if (p) return p.task || whenWords(when); // the hand-off's task for a few seconds, then its When again
    if (f?.background && f.running) return "in the background: its chain is not followed";
    return whenWords(when);
  };
  return (
    <div className="mp-canvas" data-testid="map-canvas">
      <div className="mp-zoom"><TopLine fresh={v.strip.filter((b) => b.isNew && !b.ghost).length} /><ZoomButtons zoom={zoom} zoomAt={nav.zoomAt} fit={nav.fit} /></div>
      <div className="mp-scroll rc-scroll" ref={scroll} tabIndex={0} data-pan="1" title={NAV_HELP} data-testid="map-scroll" aria-label="The map">
        <div className="mp-world-size" style={{ width: g.w * zoom, height: g.h * zoom }}>
          <div className="mp-world" ref={world} data-testid="map-world" data-zoom={zoom.toFixed(3)} data-hover={hover || undefined} data-lit={L.ov ? L.mode : undefined}
               style={{ width: g.w, height: g.h, transform: `scale(${zoom})` }}>
            <svg className="mp-lines" width={g.w} height={g.h} aria-hidden="true">
              {g.lines.map((l) => (
                <path key={l.key} d={l.d} className={`mp-line ${lit(l.from, l.to)}`} data-ghost={l.ghost || undefined} data-testid="map-line"
                      data-from={l.from} data-to={l.to} markerEnd="url(#mp-head)" data-helper={l.helper || undefined}
                      data-pulse={pulse(l.from, l.to) ? "1" : undefined} data-fired={fired(l.from, l.to)?.t ? "1" : undefined} />
              ))}
              {g.lines.filter((l) => pulse(l.from, l.to)).map((l) => ( // the hand-off moving along the line (no travel when motion is reduced)
                <circle key={`p${l.key}${pulse(l.from, l.to)!.t}`} r="5" className="mp-pulse-dot" data-testid="map-pulse">
                  <animateMotion dur="1.4s" repeatCount="1" fill="freeze" path={l.d} />
                </circle>
              ))}
              <defs><marker id="mp-head" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" className="mp-tip" /></marker></defs>
            </svg>
            {g.lines.filter((l) => !l.helper).map((l) => (
              <button key={`l${l.key}`} type="button" className={`mp-label mono ${lit(l.from, l.to)}`} data-ghost={l.ghost || undefined}
                      data-testid="map-label" data-from={l.from} data-to={l.to} style={{ left: l.lx, top: l.ly, width: LABEL_W, height: LABEL_H }}
                      data-pulse={pulse(l.from, l.to) ? "1" : undefined} data-skipped={fired(l.from, l.to)?.skipped ? "1" : undefined}
                      title={`${l.from} hands work to ${l.to}: ${whenWords(l.when)}${fired(l.from, l.to)?.task ? `; last hand-off: ${fired(l.from, l.to)!.task}` : ""}${fired(l.from, l.to)?.skipped ? `; not taken: ${fired(l.from, l.to)!.skipped}` : ""}${locked || l.ghost ? "" : " (click: change the When, or take the line out)"}`}
                      onClick={() => !locked && !l.ghost && openWhen(l.from, l.to, false)}>
                {words(l.from, l.to, l.when)}
              </button>
            ))}
            {g.boxes.map((b) => (
              <MapBox key={b.id} b={b} facts={detail?.boxes[b.id]} mainFacts={detail?.main}
                      style={{ position: "absolute", left: b.x, top: b.y, width: BOX_W, minHeight: b.h }} />
            ))}
          </div>
        </div>
      </div>
      {more && <span className="cw-line mp-more" data-testid="map-more" title={NAV_HELP}>more than fits at a readable size: scroll or drag the background, or Ctrl + wheel to zoom</span>}
      <svg className="mp-rubber" data-testid="map-rubber" aria-hidden="true"><path className="mp-line hot" /></svg>
      <span className="mp-drag-ghost mono" data-testid="map-drag-ghost" hidden />
    </div>
  );
}
