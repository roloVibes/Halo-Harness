// The card glow explained by the card itself (3.1.5.0 R3): hovering a card's
// live badge or its state glyph opens this legend beside it -- the four
// states, each in its own colour, what it means and when the glow comes and
// goes (glow.ts GLOW), the card's own state marked. A glass box with the HUD
// brackets, fixed to the viewport so the canvas's zoom and scroll never clip it.
import { createPortal } from "react-dom";
import { GLOW, useLegend } from "./glow";

export function GlowLegend() {
  const at = useLegend();
  if (!at) return null;
  const left = Math.max(8, Math.min(at.x, window.innerWidth - 336));
  const top = at.y + 220 > window.innerHeight ? Math.max(8, at.y - 240) : at.y;
  return createPortal(
    <div className="rc-legend holo-frame glass" role="tooltip" data-testid="roles-glow-legend" data-state={at.state || "none"} data-card={at.card} style={{ left, top }}>
      <span className="holo-corners" aria-hidden="true" />
      <div className="rc-legend-head mono">THE CARD'S GLOW</div>
      {GLOW.map((g) => (
        <div key={g.state} className="rc-legend-row" data-holo-state={g.state} data-testid="roles-glow-legend-row" data-on={g.state === at.state || undefined}>
          <span className="rc-legend-swatch" aria-hidden="true" />
          <b className="rc-legend-label">{g.label}</b>
          <span className="rc-legend-color mono">{g.color}</span>
          <span className="rc-legend-when">{g.when}</span>
        </div>
      ))}
    </div>,
    document.body,
  );
}
