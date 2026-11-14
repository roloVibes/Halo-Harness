// The Agents tab's list (3.6.0.0 R1; the approved mock's left column): + New agent, then YOURS (yours and this project's,
// each tagged `new` when made in the last day and `not used yet` when no workflow or map names it), then STARTERS TO
// COPY (a click copies one into the form as yours, not saved yet). While the builder's preview would make an agent it
// shows here as a dashed ghost row. Hover a row: its whole line; click: the form.
import { Button } from "../../lib/ui";
import { useBuilder } from "./builderStore";
import { copyFrom, newAgent, openAgent, useCrew } from "./store";
import type { Row } from "./types";

function Item({ r, on }: { r: Row; on: boolean }) {
  const unused = !r.used.length;
  const tip = `${r.name}: ${r.does}${r.used.length ? `\nused by ${r.used.join(", ")}` : "\nnot used yet: no workflow or map names it"}`;
  return (
    <button type="button" className="cw-item" aria-current={on} onClick={() => void openAgent(r.name, r.scope)} title={tip}
            data-testid="crew-item" data-name={r.name} data-scope={r.scope}>
      <span className="cw-item-head">
        <b className="cw-item-name">{r.name}</b>
        {r.scope === "project" && <span className="cw-tag" data-tag="project">this project's</span>}
        {r.new && <span className="cw-tag" data-tag="new">new</span>}
        {unused && <span className="cw-tag" data-tag="unused">not used yet</span>}
        {r.problems.length > 0 && <span className="cw-tag" data-tag="bad" title={r.problems.join("\n")}>problem</span>}
      </span>
      <span className="cw-item-does">{r.does}</span>
    </button>
  );
}

function Ghosts() {
  const pending = useBuilder((s) => s.pending); // the array itself: a selector that makes a new one each read loops
  const made = pending.filter((c) => c.ticked && c.kind === "create");
  return (
    <>
      {made.map((c) => (
        <div key={c.id} className="cw-item" data-ghost="1" data-testid="crew-ghost" title={c.summary}>
          <span className="cw-item-head">
            <b className="cw-item-name">{c.target.split(":")[1]}</b>
            <span className="cw-tag" data-tag="new">preview</span>
          </span>
          <span className="cw-item-does">{c.summary}</span>
        </div>
      ))}
    </>
  );
}

export function CrewList() {
  const agents = useCrew((s) => s.agents);
  const starters = useCrew((s) => s.starters);
  const open = useCrew((s) => s.open);
  const loaded = useCrew((s) => s.loaded);
  const error = useCrew((s) => s.error);
  const isOn = (r: Row) => !!open && open.name === r.name && open.scope === r.scope;
  return (
    <nav className="cw-list" aria-label="Your agents" data-testid="crew-list">
      <Button variant="primary" className="cw-new" onClick={newAgent} data-testid="crew-new">+ New agent</Button>
      <div className="cw-group mono">Yours</div>
      <Ghosts />
      {agents.map((r) => <Item key={`${r.scope}:${r.name}`} r={r} on={isOn(r)} />)}
      {loaded && !agents.length && <p className="cw-hint" data-testid="crew-none">None yet: + New agent, or copy a starter below.</p>}
      {agents.some((r) => !r.used.length) && <p className="cw-hint">"not used yet": no workflow and no map names it.</p>}
      {error && <p className="cw-hint" data-tone="bad">{error}</p>}
      <div className="cw-group mono">Starters to copy</div>
      {starters.map((r) => (
        <button key={r.name} type="button" className="cw-item" onClick={() => void copyFrom(r.name, "starter")} title={`Copy ${r.name}: ${r.does}`}
                data-testid="crew-starter" data-name={r.name}>
          <span className="cw-item-head"><b className="cw-item-name">{r.name}</b><span className="cw-tag">copy</span></span>
          <span className="cw-item-does">{r.does}</span>
        </button>
      ))}
    </nav>
  );
}
