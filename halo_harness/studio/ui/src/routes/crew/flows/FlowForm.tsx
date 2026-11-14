// The workflow form (3.6.0.0 R2; the approved mock's right side, in the order he thinks): the name and where it is
// used; what it is for, with Write it for me (it fills the builder box below: the steps come back as a preview, drawn
// here as ghost steps); the steps, in order (StepRow.tsx) with + Add a step; what it costs and writes; Try it; Save /
// Discard / Copy / Delete (Delete asks on the page). Beside it, the steps drawn (Drawn.tsx). Nothing is written until Save.
import { Button, TextBox } from "../../../lib/ui";
import { prefill, useBuilder } from "../builderStore";
import { useCrew } from "../store";
import type { Change } from "../types";
import { Drawn, type DrawnStep } from "./Drawn";
import { askDeleteFlow, addStep, copyOpenFlow, costNow, discardFlow, flowDirty, newFlow, openFlow, removeFlow, saveFlow, setAdding, setFlow, useFlows } from "./flowStore";
import { FlowTry } from "./FlowTry";
import { makeForStep } from "./makeIt";
import { GhostStep, StepRow } from "./StepRow";

function Empty() {
  const n = useFlows((s) => s.flows.length);
  return (
    <div className="cw-empty" data-testid="flow-empty">
      <h2 className="cw-title">{n ? "Pick a workflow on the left" : "Make your first workflow"}</h2>
      <p className="cw-line">A workflow is your agents in steps, in order: each step's agents work at the same time and hand on to the next.
        Make one here, copy a starter from the list, or describe it in the builder box below.</p>
      <div className="cw-row"><Button variant="primary" onClick={newFlow} data-testid="flow-empty-new">+ New workflow</Button></div>
    </div>
  );
}

function AddStep() {
  const adding = useFlows((s) => s.adding);
  const mine = useCrew((s) => s.agents);
  const starters = useCrew((s) => s.starters);
  if (!adding) return <Button variant="primary" onClick={() => setAdding(true)} data-testid="flow-add-step">+ Add a step</Button>;
  return (
    <div className="fl-picker" data-testid="flow-picker">
      <div className="cw-row"><b>A new step with which agent?</b><Button onClick={() => setAdding(false)} data-testid="flow-picker-close">Close</Button></div>
      {[...mine, ...starters].map((a) => (
        <button key={`${a.scope}:${a.name}`} type="button" className="cw-item" onClick={() => addStep(a.name, a.does)} title={a.does}
                data-testid="flow-pick-agent" data-name={a.name}>
          <span className="cw-item-head"><b className="cw-item-name">{a.name}</b>{a.scope === "starter" && <span className="cw-tag">starter</span>}</span>
          <span className="cw-item-does">{a.does}</span>
        </button>
      ))}
      <button type="button" className="cw-item" onClick={makeForStep} data-testid="flow-pick-new">
        <span className="cw-item-head"><b className="cw-item-name">+ Make a new agent for it</b></span>
        <span className="cw-item-does">opens the agent form; Save there and you come back here with the step added</span>
      </button>
    </div>
  );
}

function SaveBar() {
  const s = useFlows((x) => x);
  const isDirty = flowDirty(s);
  const name = s.form?.name || "";
  if (s.asking === "delete")
    return (
      <div className="cw-savebar" data-testid="flow-delete-ask">
        <span className="cw-line">{s.maps.length ? `${name} is on the map ${s.maps.join(", ")}: take it off there first.` : `Delete ${name}? Its file goes; nothing else changes.`}</span>
        {!s.maps.length && <Button variant="danger" onClick={() => void removeFlow()} data-testid="flow-delete-yes">Delete it</Button>}
        <Button onClick={() => askDeleteFlow(false)} data-testid="flow-delete-no">Keep it</Button>
      </div>
    );
  return (
    <div className="cw-savebar" data-testid="flow-savebar">
      <Button variant="primary" disabled={!isDirty || s.busy || s.open?.scope === "starter"} onClick={() => void saveFlow()} data-testid="flow-save">Save</Button>
      <Button disabled={!isDirty} onClick={discardFlow} data-testid="flow-discard">Discard changes</Button>
      <Button onClick={copyOpenFlow} data-testid="flow-copy">Copy</Button>
      {!!s.open?.name && <Button variant="danger" onClick={() => askDeleteFlow(true)} data-testid="flow-delete">Delete...</Button>}
      <span className="cw-line" data-testid="flow-note">{s.note || (isDirty ? "Not saved yet." : "")}</span>
    </div>
  );
}

const forThis = (c: Change, name: string) => c.target === `workflow:${name}`;
const NONE: string[] = [];

export function FlowForm() {
  const w = useFlows((s) => s.form);
  const maps = useFlows((s) => s.maps);
  const stale = useFlows((s) => s.stale);
  const open = useFlows((s) => s.open);
  const now = useFlows(costNow); // the band of the form as it stands (null while it is read)
  const cost = now?.cost;
  const writes = now?.writes || NONE;
  const problems = now?.problems || NONE;
  const pending = useBuilder((s) => s.pending, "workflows");
  const meta = useBuilder((s) => s.meta, "workflows");
  if (!w) return <Empty />;
  const mine = pending.filter((c) => c.ticked && forThis(c, w.name));
  const ghosts = mine.filter((c) => c.ghost?.op === "step_add");
  const notes = (i: number) => mine.filter((c) => c.ghost && c.ghost.op !== "step_add" && c.ghost.index === i + 1);
  const drawn: DrawnStep[] = [...w.steps, ...ghosts.map((c) => ({ ...c.ghost!.step!, ghost: true }))];
  return (
    <div className="fl-page" data-testid="flow-form" data-name={w.name}>
      <div className="cw-form fl-form">
        {stale && (
          <div className="cw-stale" data-testid="flow-stale">
            <span className="cw-line">The builder changed {open?.name} while you had edits here.</span>
            <Button size="sm" onClick={() => open && void openFlow(open.name, open.scope)}>Reload it (your edits go)</Button>
          </div>
        )}
        <label className="cw-field">
          <span className="cw-label mono">Name</span>
          <input className="input mono" value={w.name} spellCheck={false} data-testid="flow-name"
                 onChange={(e) => setFlow({ name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 48) })} />
          <span className="cw-line" data-testid="flow-used">{maps.length ? `On the map ${maps.join(", ")}.`
            : "Not on a map yet (the Map tab comes next). A session's Workflow tool can run it by its name once it is saved."}</span>
        </label>
        <label className="cw-field">
          <span className="cw-label mono">What it is for</span>
          <TextBox value={w.for} onChange={(e) => setFlow({ for: e.target.value })} placeholder="In your words: what it is for, what comes in, what it hands back" data-testid="flow-for" />
        </label>
        <div className="cw-row">
          <Button onClick={() => prefill("Draft the steps from what it is for", "workflows")} disabled={!w.for.trim()} data-testid="flow-write">Write it for me</Button>
          <span className="cw-line">Fills the builder box below: it drafts the steps from your agents and proposes a new one only when none fits
            {meta?.model ? ` (${meta.model}, ${meta.typical})` : ""}. Nothing is saved until you Save.</span>
        </div>
        <div className="cw-field" data-testid="flow-steps">
          <span className="cw-label mono">The steps, in order</span>
          {w.steps.map((s, i) => <StepRow key={i} s={s} i={i} n={w.steps.length} notes={notes(i)} />)}
          {ghosts.map((c, k) => <GhostStep key={c.id} c={c} n={w.steps.length + k + 1} />)}
          {!w.steps.length && !ghosts.length && <p className="cw-hint">No steps yet: + Add a step picks one of your agents (or makes one).</p>}
          <AddStep />
        </div>
        <div className="cw-field" data-testid="flow-cost">
          <span className="cw-label mono">What it costs and writes</span>
          <span className="cw-line mono" data-testid="flow-cost-line">{cost?.line || "reading the prices..."}</span>
          {writes.map((l) => <span key={l} className="cw-line" data-testid="flow-writes">{l}</span>)}
          {problems.map((p) => <span key={p} className="cw-line" data-tone="bad" data-testid="flow-problem">{p}</span>)}
        </div>
        <FlowTry w={w} />
        <SaveBar />
      </div>
      <Drawn steps={drawn} />
    </div>
  );
}
