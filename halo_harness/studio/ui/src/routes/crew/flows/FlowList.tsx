// The Workflows tab's list (3.6.0.0 R2; the approved mock's left column): + New workflow, then YOURS (yours and this
// project's, each tagged `on the map` or `not on the map`; in this version nothing is on a map yet and one line says
// so), then STARTERS TO COPY (a click copies one into the form as yours, not saved yet). A workflow the builder's
// preview would make shows as a dashed ghost row. Hover a row: its whole line; click: the form.
import { Button } from "../../../lib/ui";
import { useBuilder } from "../builderStore";
import type { FlowRow } from "../types";
import { copyFlowFrom, newFlow, openFlow, useFlows } from "./flowStore";

const stepsWord = (n: number) => `${n} step${n === 1 ? "" : "s"}`;

function Item({ r, on }: { r: FlowRow; on: boolean }) {
  const onMap = r.maps.length > 0;
  const tip = `${r.name}: ${r.for}\n${stepsWord(r.steps?.length || 0)}: ${(r.steps || []).map((s) => s.name).join(" -> ")}\n` +
    (onMap ? `on the map ${r.maps.join(", ")}` : "not on a map yet");
  return (
    <button type="button" className="cw-item" aria-current={on} onClick={() => void openFlow(r.name, r.scope)} title={tip}
            data-testid="flow-item" data-name={r.name} data-scope={r.scope}>
      <span className="cw-item-head">
        <b className="cw-item-name">{r.name}</b>
        {r.scope === "project" && <span className="cw-tag" data-tag="project">this project's</span>}
        {r.new && <span className="cw-tag" data-tag="new">new</span>}
        <span className="cw-tag" data-tag={onMap ? "on" : "unused"} data-testid="flow-item-map">{onMap ? "on the map" : "not on the map"}</span>
        {r.problems.length > 0 && <span className="cw-tag" data-tag="bad" title={r.problems.join("\n")}>problem</span>}
      </span>
      <span className="cw-item-does">{stepsWord(r.steps?.length || 0)} · {r.for}</span>
    </button>
  );
}

function Ghosts() {
  const pending = useBuilder((s) => s.pending, "workflows"); // the array itself: a selector that makes a new one each read loops
  const made = pending.filter((c) => c.ticked && c.kind === "create" && c.target.startsWith("workflow:"));
  return (
    <>
      {made.map((c) => (
        <div key={c.id} className="cw-item" data-ghost="1" data-testid="flow-ghost" title={c.summary}>
          <span className="cw-item-head"><b className="cw-item-name">{c.target.split(":")[1]}</b><span className="cw-tag" data-tag="new">preview</span></span>
          <span className="cw-item-does">{c.summary}</span>
        </div>
      ))}
    </>
  );
}

export function FlowList() {
  const mine = useFlows((s) => s.flows);
  const starters = useFlows((s) => s.starters);
  const open = useFlows((s) => s.open);
  const loaded = useFlows((s) => s.loaded);
  const error = useFlows((s) => s.error);
  const isOn = (r: FlowRow) => !!open && open.name === r.name && open.scope === r.scope;
  return (
    <nav className="cw-list" aria-label="Your workflows" data-testid="flow-list">
      <Button variant="primary" className="cw-new" onClick={newFlow} data-testid="flow-new">+ New workflow</Button>
      <div className="cw-group mono">Yours</div>
      <Ghosts />
      {mine.map((r) => <Item key={`${r.scope}:${r.name}`} r={r} on={isOn(r)} />)}
      {loaded && !mine.length && <p className="cw-hint" data-testid="flow-none">None yet: + New workflow, copy a starter below, or describe one in the builder box.</p>}
      {mine.length > 0 && !mine.some((r) => r.maps.length) && (
        <p className="cw-hint" data-testid="flow-no-map">Nothing is on a map yet: the Map tab, where you connect workflows, comes in the next version.</p>
      )}
      {error && <p className="cw-hint" data-tone="bad">{error}</p>}
      <div className="cw-group mono">Starters to copy</div>
      {starters.map((r) => (
        <button key={r.name} type="button" className="cw-item" onClick={() => void copyFlowFrom(r.name, "starter")} title={`Copy ${r.name}: ${r.for}`}
                data-testid="flow-starter" data-name={r.name}>
          <span className="cw-item-head"><b className="cw-item-name">{r.name}</b><span className="cw-tag">copy</span></span>
          <span className="cw-item-does">{stepsWord(r.steps?.length || 0)} · {r.for}</span>
        </button>
      ))}
    </nav>
  );
}
