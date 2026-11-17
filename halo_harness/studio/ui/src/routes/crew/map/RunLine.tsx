// A line of the run's drawing (3.6.0.2 R16 R17): every hand-off lights the line it travels while it is in flight
// (`data-lit=live`: its start has no end, a live row carries it, the session is busy -- overlayHops.ts inFlight), then a
// quieter trace whose weight steps at 1 / 2 / 3+ hand-offs (`data-lit=trace`, `data-hops` 1 | 2 | 3), the newest marked
// (`data-last`), hover "Carried {n} hand-off(s); last at {t}: {few words}". A line nothing travelled is never lit. A
// dashed line no line of the map drew (a workflow on no box, under its caller) is `data-off` in `--off-map` on a map of
// his, hover "Not on the map: {sender} started this itself". Weights and colours: styles/map-down.css, by attribute.
// R18: with `onPick` a wider transparent twin (`data-hit`, a 12 px stroke: the hit area >= 10 px) takes the click: the
// step-in card for the agent travelling it, or its state ("Starts when ..." for a line nothing travelled).
import { whenWords } from "./mapTypes";
import { offHover, startsWhen, traceHover } from "./truth";
import type { RoutedDown } from "./layoutDown";
import type { Lit } from "./LitMini";

const FEW = 8; // the task's first words in the hover

export const fewWords = (task: string): string => task.trim().split(/\s+/).filter(Boolean).slice(0, FEW).join(" ");

export type LinePick = (l: RoutedDown, text: string) => void;

export function RunLine({ l, lit, onPick }: { l: RoutedDown; lit: Pick<Lit, "totals" | "live">; onPick?: LinePick }) {
  const k = `${l.from}>${l.to}`, c = lit.totals.lines[k];
  const live = lit.live.has(k);
  const hover = l.off ? offHover(l.from) : c ? traceHover(c.n, c.last, fewWords(c.task)) : "";
  const state = hover || startsWhen(whenWords(l.when), l.from);
  return (
    <>
    <path d={l.d} className="mp-line" data-from={l.from} data-to={l.to} data-helper={l.helper || undefined} data-off={l.off ? "1" : undefined}
          data-lit={live ? "live" : c ? "trace" : undefined} data-hops={c ? Math.min(3, c.n) : undefined}
          data-last={c && lit.totals.last === k ? "1" : undefined} data-hover={hover || undefined}>
      {hover && <title>{hover}</title>}
    </path>
    {onPick && (
      <path d={l.d} className="mp-hit" data-hit={k} onClick={(e) => (e.stopPropagation(), onPick(l, state))}>
        <title>{state}</title>
      </path>
    )}
    </>
  );
}
