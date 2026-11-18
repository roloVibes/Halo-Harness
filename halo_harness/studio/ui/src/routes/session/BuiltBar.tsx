// What the session just built, over Session's Live drawing (3.6.0.2 R30 R31), INSIDE the drawing's own box (MapDown.tsx
// puts it at the top of the room the drawing takes), so it takes no room until a build lands and no control moves when it
// does: the drawing moves down once.
// - the pair "Running: {A} | Just built: {B}", each a button (built.ts chooses Just built once, else marks its tab), only
//   while the session built another map: with one map there is no such row (the truth block above names it); only
//   Running is lit (MapDown draws Just built calm);
// - the head, truth.ts's words: a workflow on no map (with [Open in Workflows], which alone changes the section), a
//   change to the running map, any other map. Its words are never cut (R10, the owner's rule: a text box fits its text):
//   they wrap whole across the drawer's width, its buttons sit on their own row under them, and its height is taken
//   from a hidden twin of the same words measured at the drawer's width before it is shown (as R20's truth block), so
//   nothing moves after the head's first draw.
import { useLayoutEffect, useRef, useState } from "react";
import { goSection } from "../../lib/store";
import { setAgentsView } from "../agents/store";
import { openFlow } from "../crew/flows/flowStore";
import { pressPair, useBuilt } from "../crew/map/built";
import type { LitSession } from "../crew/map/litStore";
import { justBuilt, mapName, pair, type Line } from "../crew/map/truth";

function BuiltHead({ head, kind, flows }: { head: Line; kind: string; flows: () => void }) {
  const twin = useRef<HTMLSpanElement>(null);
  const [h, setH] = useState(0);
  useLayoutEffect(() => { // the twin's height at the drawer's width, read before the first paint and on every resize
    const el = twin.current;
    if (!el) return;
    const read = () => setH((o) => (o === el.offsetHeight ? o : el.offsetHeight));
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div className="mp-built-head" data-testid="session-built-head" data-kind={kind}>
      <span className="mp-built-twin" ref={twin} aria-hidden="true">{head.text}</span>
      <p className="mp-built-text" data-testid="session-built-text" style={{ minHeight: h || undefined }}>{head.text}</p>
      {head.act === "open-workflows" && (
        <div className="mp-built-acts">
          <button type="button" className="mp-link" data-testid="session-built-open" onClick={flows}>{head.label}</button>
        </div>
      )}
    </div>
  );
}

export function BuiltBar({ s }: { s: LitSession }) {
  const b = useBuilt((x) => x.last[s.sid]);
  const which = useBuilt((x) => x.which[s.sid]) || "running";
  const marked = useBuilt((x) => !!x.marked[s.sid]);
  const two = b?.kind === "other" && !!b.map;
  const head = b?.kind ? justBuilt(b.kind, { workflow: b.workflow, t: b.t, map: b.map, next: b.next }) : null;
  if (!two && !head) return null;
  const [run, just] = pair(mapName(s.map || "auto", s.plain !== false), b?.map || "");
  const flows = () => { // R31: Agents -> Workflows with W open, on this press only
    setAgentsView("workflows");
    void openFlow(b!.workflow);
    goSection("agents", "workflows");
  };
  return (
    <div className="mp-built" data-testid="session-built">
      {two && (
        <div className="mp-pair" data-testid="session-map-pair">
          <button type="button" className="mp-pair-btn" data-which="running" aria-pressed={which !== "built"} title={run}
                  onClick={() => pressPair(s.sid, "running")}>{run}</button>
          <span className="mp-pair-sep" aria-hidden="true"> | </span>
          <button type="button" className="mp-pair-btn" data-which="built" aria-pressed={which === "built"} title={just}
                  data-new={marked ? "" : undefined} onClick={() => pressPair(s.sid, "built")}>{just}</button>
        </div>
      )}
      {head && <BuiltHead key={head.text} head={head} kind={b!.kind!} flows={flows} />}
    </div>
  );
}
