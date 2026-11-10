// What every hover card says, in one shape (3.3.16.1): a title line, one sentence of what the box IS (two lines at most,
// CSS-clamped), then a `dl` of at most eight rows (a label in the inspector's small mono caps, its value beside it; a row
// whose fact is unknown is left out, never printed as "?" or "0"), then a NOW block when the box is doing something,
// then one faint line saying what a click does. The text wraps inside its row; only the IS line is cut, by CSS.
import type { ReactNode } from "react";

export type HoverRow = [label: string, value: ReactNode];
export const MAX_ROWS = 8;

const slug = (label: string) => label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const known = (v: ReactNode) => v !== null && v !== undefined && v !== false && v !== "";

export function HoverBody({ title, is, rows, now, foot = "Click for everything" }: { title: string; is?: string; rows: HoverRow[]; now?: ReactNode; foot?: string }) {
  const shown = rows.filter(([, v]) => known(v)).slice(0, MAX_ROWS);
  return (
    <>
      <div className="hc-title" data-testid="hover-card-title">{title}</div>
      {is && <p className="hc-is" data-testid="hover-card-is">{is}</p>}
      {shown.length > 0 && (
        <dl className="hc-rows">
          {shown.map(([k, v]) => (
            <div key={k} className="hc-row" data-row={slug(k)} data-testid="hover-card-row">
              <dt className="mono">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {known(now) && (
        <div className="hc-now" data-testid="hover-card-now">
          <span className="hc-now-k mono">now</span>
          <span className="hc-now-v">{now}</span>
        </div>
      )}
      <div className="hc-foot" data-testid="hover-card-foot">{foot}</div>
    </>
  );
}
