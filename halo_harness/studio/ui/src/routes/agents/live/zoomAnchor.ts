// The thing under the pointer stays under it (3.3.18.0 "The living canvas" part 4): a zoom -- the wheel with Ctrl or
// Cmd, the bar's - / + / level switch, the keys -- first marks what is at its anchor (the pointer, else the middle of the
// view): an agent's box, a block's or a group's bar, and the block or group around it. After the canvas has drawn at the
// new zoom (and, when the level changed, laid out again), the scroll moves so that thing sits where it sat. Something
// that is not drawn at the new level (an agent at far) is found by the block or group it was in; nothing at all, by the
// point it was in the drawing. 3.4.1.3: the wheel, the keys and the drag live in lib/canvasNav.ts (the same on every
// drawing); this keeps the anchor.
import { useLayoutEffect, useRef, type RefObject } from "react";

type Mark = { sels: string[]; fx: number; fy: number; px: number; py: number; cx: number; cy: number };
const HIT = '[data-testid="roles-live-node"], [data-testid="live-block-bar"], [data-testid="live-group-bar"]';

function selsOf(hit: Element, x: number, y: number): string[] {
  const d = (hit as HTMLElement).dataset;
  const out: string[] = [];
  if (d.testid === "roles-live-node") out.push(`[data-testid="roles-live-node"][data-agent="${d.agent}"]`);
  const id = d.block || d.group || "";
  const around = [...document.querySelectorAll<HTMLElement>('[data-testid="live-block"], [data-testid="live-group"]')]
    .find((b) => { const r = b.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; });
  for (const g of [id, around?.dataset.block || around?.dataset.group || ""].filter(Boolean))
    out.push(`[data-testid="live-block-bar"][data-block="${g}"]`, `[data-testid="live-group-bar"][data-group="${g}"]`);
  return out;
}

export function useZoomAnchor(scroll: RefObject<HTMLDivElement | null>, zoom: number, layoutKey: string, setZoom: (z: number) => void) {
  const pending = useRef<Mark | null>(null);
  const zref = useRef(zoom);
  zref.current = zoom;
  /** Zoom to `z` with the anchor at (px, py) in the view (default: its middle). */
  const zoomAt = (z: number, px?: number, py?: number) => {
    const el = scroll.current;
    if (!el) return setZoom(z);
    const r = el.getBoundingClientRect();
    const ax = px ?? el.clientWidth / 2, ay = py ?? el.clientHeight / 2;
    const hit = document.elementFromPoint(r.left + ax, r.top + ay)?.closest(HIT);
    const hr = hit?.getBoundingClientRect();
    pending.current = { sels: hit ? selsOf(hit, r.left + ax, r.top + ay) : [], fx: hr ? (r.left + ax - hr.left) / hr.width : 0, fy: hr ? (r.top + ay - hr.top) / hr.height : 0,
                        px: ax, py: ay, cx: (el.scrollLeft + ax) / zref.current, cy: (el.scrollTop + ay) / zref.current };
    setZoom(z);
  };
  useLayoutEffect(() => {
    const p = pending.current, el = scroll.current;
    if (!p || !el) return;
    pending.current = null;
    const r = el.getBoundingClientRect();
    const idx = p.sels.findIndex((sel) => !!document.querySelector(sel));
    const at = idx >= 0 ? document.querySelector<HTMLElement>(p.sels[idx]) : null;
    if (at) {
      const hr = at.getBoundingClientRect();
      const keep = idx === 0; // the same thing: the same spot on it; its block or group: its middle
      el.scrollLeft += hr.left + (keep ? p.fx : 0.5) * hr.width - (r.left + p.px);
      el.scrollTop += hr.top + (keep ? p.fy : 0.5) * hr.height - (r.top + p.py);
    } else {
      el.scrollLeft = p.cx * zoom - p.px;
      el.scrollTop = p.cy * zoom - p.py;
    }
  }, [zoom, layoutKey]);
  return zoomAt;
}
