// The zoom buttons for people without a wheel (3.4.1.3, lib/canvasNav.ts): - , the zoom (a click: 100%), + and Fit,
// the help line on hover. Drawn where a canvas has no bar of its own (Session's Map); Live, Cast and the design pack's
// artboards keep the same four in their bars.
import { clampZoom, NAV_HELP } from "../canvasNav";

export function ZoomButtons({ zoom, zoomAt, fit }: { zoom: number; zoomAt: (z: number) => void; fit: () => void }) {
  return (
    <span className="segmented cz-zoom" role="group" aria-label="Zoom" title={NAV_HELP} data-testid="canvas-zoom">
      <button type="button" onClick={() => zoomAt(clampZoom(zoom / 1.2))} aria-label="Zoom out" data-testid="canvas-zoom-out">-</button>
      <button type="button" onClick={() => zoomAt(1)} title="Back to 100%" data-testid="canvas-zoom-level">{Math.round(zoom * 100)}%</button>
      <button type="button" onClick={() => zoomAt(clampZoom(zoom * 1.2))} aria-label="Zoom in" data-testid="canvas-zoom-in">+</button>
      <button type="button" onClick={fit} title="Fit the drawing to the panel (0, or double-click the background)" data-testid="canvas-fit">Fit</button>
    </span>
  );
}
