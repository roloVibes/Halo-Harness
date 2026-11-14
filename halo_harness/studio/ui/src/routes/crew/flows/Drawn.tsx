// The steps, drawn (3.6.0.0 R2; the design: "a read-out of the list: a box per step, an arrow between, a loop mark for a
// repeat. It draws itself and is never wired"). It reads the form as it stands, ghost steps of the builder's preview
// dashed at the end. Zoom the house way (lib/canvasNav.ts: Ctrl / Cmd + wheel, pinch, - % + Fit, 0, a double-click),
// and R8: when its box changes width it fits again unless you zoomed it by hand; it never fits below the zoom where its
// 13 px text is 12 px on screen -- past that it scrolls. A box per step; hover: its whole line.
import { useLayoutEffect, useRef, useState } from "react";
import { fitScale, NAV_HELP, recallZoom, useCanvasNav, useZoomPoint } from "../../../lib/canvasNav";
import { ZoomButtons } from "../../../lib/ui/ZoomButtons";
import type { Step, When } from "../types";

export const BOX_W = 210;
const BOX_H = 76;
const GAP = 34;
const PAD = 12;
const LOOP = 44;
const TEXT_PX = 13;

export function whenLine(w?: When): string {
  if (!w || w === "always") return "always";
  if (w === "ask") return "only when you ask";
  return "needs" in w ? `when the task needs ${w.needs.join(", ")}` : `when the task says ${w.says.join(", ")}`;
}

export type DrawnStep = Step & { ghost?: boolean };

export function layout(steps: DrawnStep[]) {
  let y = PAD;
  const boxes = steps.map((s, i) => {
    const b = { s, i, x: PAD, y, h: BOX_H + (s.repeat ? 20 : 0) };
    y += b.h + GAP;
    return b;
  });
  return { boxes, w: PAD * 2 + BOX_W + LOOP, h: Math.max(y - GAP + PAD, 80) };
}

export function Drawn({ steps }: { steps: DrawnStep[] }) {
  const scroll = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(() => recallZoom("flow-drawn") ?? 1);
  const g = layout(steps);
  const at = useZoomPoint(scroll, zoom, setZoom);
  const fit = () => {
    const el = scroll.current;
    if (el) setZoom(fitScale(el.clientWidth, el.clientHeight, g.w, g.h, { max: 1.25, textPx: TEXT_PX, pad: 8 }).zoom);
  };
  const nav = useCanvasNav(scroll, { zoom, zoomAt: at, fit, id: "flow-drawn", min: 0.5, max: 2 });
  const drawn = steps.length > 0;
  useLayoutEffect(() => { // the first drawing fits its box (later: R8, when the box changes width)
    if (drawn && !nav.byHand()) fit();
  }, [drawn]); // eslint-disable-line react-hooks/exhaustive-deps
  const el = scroll.current;
  const more = drawn && !!el && (g.w * zoom > el.clientWidth + 2 || g.h * zoom > el.clientHeight + 2);
  return (
    <aside className="fd" aria-label="The steps, drawn" data-testid="flow-drawn">
      <div className="fd-head">
        <span className="cw-label mono">The steps, drawn</span>
        <ZoomButtons zoom={zoom} zoomAt={nav.zoomAt} fit={nav.fit} />
      </div>
      <div className="fd-scroll rc-scroll" ref={scroll} tabIndex={0} data-pan="1" title={NAV_HELP} data-testid="flow-drawn-scroll">
        {!steps.length && <p className="cw-hint fd-none">No steps yet: + Add a step, or ask the builder.</p>}
        {!!steps.length && (
          <div className="fd-world" style={{ width: g.w * zoom, height: g.h * zoom }}>
            <div className="fd-inner" style={{ width: g.w, height: g.h, transform: `scale(${zoom})` }} data-zoom={zoom.toFixed(3)}>
              <svg className="fd-lines" width={g.w} height={g.h} aria-hidden="true">
                {g.boxes.slice(1).map((b) => (
                  <path key={`a${b.i}`} d={`M ${PAD + BOX_W / 2} ${b.y - GAP + 2} L ${PAD + BOX_W / 2} ${b.y - 4}`} className="fd-arrow" markerEnd="url(#fd-head)" />
                ))}
                {g.boxes.filter((b) => b.s.repeat).map((b) => (
                  <path key={`l${b.i}`} className="fd-loop" markerEnd="url(#fd-head)"
                        d={`M ${PAD + BOX_W} ${b.y + b.h - 18} C ${PAD + BOX_W + 36} ${b.y + b.h - 18}, ${PAD + BOX_W + 36} ${b.y + 14}, ${PAD + BOX_W + 4} ${b.y + 14}`} />
                ))}
                <defs><marker id="fd-head" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" className="fd-tip" /></marker></defs>
              </svg>
              {g.boxes.map((b) => {
                const line = `${b.i + 1} · ${b.s.name}: ${b.s.agents.join(" + ") || "no agent yet"} · ${whenLine(b.s.when)}` +
                  (b.s.repeat ? ` · repeat until ${b.s.repeat.until}, at most ${b.s.repeat.max} times` : "");
                return (
                  <div key={b.i} className="fd-box" data-ghost={b.s.ghost || undefined} data-testid="flow-drawn-step" data-n={b.i + 1}
                       style={{ left: b.x, top: b.y, width: BOX_W, height: b.h }} title={line}>
                    <b className="fd-name">{b.i + 1} · {b.s.name || "(no name)"}</b>
                    <span className="fd-agents">{b.s.agents.join(" + ") || "no agent yet"}</span>
                    <span className="fd-when">{whenLine(b.s.when)}</span>
                    {b.s.repeat && <span className="fd-rep" data-testid="flow-drawn-loop">↺ until {b.s.repeat.until}, ≤{b.s.repeat.max}×</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
      {more && <span className="cw-line fd-more" data-testid="map-more" title={NAV_HELP}>more than fits at a readable size: scroll, or Ctrl + wheel to zoom out</span>}
    </aside>
  );
}
