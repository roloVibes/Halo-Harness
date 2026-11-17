// What the session just built, over Session's Live drawing (3.6.0.2 R30 R31), under the truth block, in room held from
// the first draw (the pair one line, the head two) so nothing below moves when a build lands:
// - the pair: one map is plain text "Running: {A}"; once the session built another map, "Running: {A} | Just built: {B}",
//   each a button (built.ts chooses Just built once, else marks its tab); only Running is lit (MapDown draws Just built
//   calm);
// - the head, truth.ts's words: a workflow on no map (with [Open in Workflows], which alone changes the section), a
//   change to the running map, any other map.
import { goSection } from "../../lib/store";
import { setAgentsView } from "../agents/store";
import { openFlow } from "../crew/flows/flowStore";
import { pressPair, useBuilt } from "../crew/map/built";
import type { LitSession } from "../crew/map/litStore";
import { justBuilt, mapName, pair } from "../crew/map/truth";

export function BuiltBar({ s }: { s: LitSession }) {
  const b = useBuilt((x) => x.last[s.sid]);
  const which = useBuilt((x) => x.which[s.sid]) || "running";
  const marked = useBuilt((x) => !!x.marked[s.sid]);
  const [run, just] = pair(mapName(s.map || "starter", s.plain !== false), b?.map || "");
  const two = b?.kind === "other" && !!b.map;
  const head = b?.kind ? justBuilt(b.kind, { workflow: b.workflow, t: b.t }) : null;
  const flows = () => { // R31: Agents -> Workflows with W open, on this press only
    setAgentsView("workflows");
    void openFlow(b!.workflow);
    goSection("agents", "workflows");
  };
  return (
    <div className="mp-built" data-testid="session-built">
      <div className="mp-pair" data-testid="session-map-pair">
        {two ? (
          <>
            <button type="button" className="mp-pair-btn" data-which="running" aria-pressed={which !== "built"} title={run}
                    onClick={() => pressPair(s.sid, "running")}>{run}</button>
            <span className="mp-pair-sep" aria-hidden="true"> | </span>
            <button type="button" className="mp-pair-btn" data-which="built" aria-pressed={which === "built"} title={just}
                    data-new={marked ? "" : undefined} onClick={() => pressPair(s.sid, "built")}>{just}</button>
          </>
        ) : <span className="mp-pair-one">{run}</span>}
      </div>
      <p className="mp-built-head" data-testid="session-built-head" data-kind={b?.kind || undefined}>
        {head?.text}
        {head?.act === "open-workflows" && (
          <>
            {" "}
            <button type="button" className="mp-link" data-testid="session-built-open" onClick={flows}>{head.label}</button>
          </>
        )}
      </p>
    </div>
  );
}
