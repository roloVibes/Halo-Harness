// The agent form (3.6.0.0 R1; the approved mock's right side): name (and where it is used), what it does with Write it
// for me (it fills the builder box below: the draft comes back as a preview), the instructions it gets, the model (the
// shared picker, Auto first), what it may use, how careful, Try it, More, and the save bar -- Save / Discard changes /
// Copy / Delete (Delete asks on the page). Nothing is written until Save.
import { useEffect } from "react";
import { Button, TextBox } from "../../lib/ui";
import { ModelSelect } from "../shared/ModelSelect";
import { prefill, useBuilder } from "./builderStore";
import { More } from "./More";
import { askDelete, copyOpen, crew, dirty, discard, newAgent, openAgent, remove, save, setForm, useCrew } from "./store";
import { TryIt } from "./TryIt";
import { estimateFor, useTry } from "./tryStore";
import { Careful, Uses } from "./Uses";

const AUTO = { label: "Auto", model: "", text: "Auto: Halo picks the model per task" };

function Empty() {
  const n = useCrew((s) => s.agents.length);
  return (
    <div className="cw-empty" data-testid="crew-empty">
      <h2 className="cw-title">{n ? "Pick an agent on the left" : "Make your first agent"}</h2>
      <p className="cw-line">An agent is a name, what it does, a model, what it may use and how careful it is. Make one here, copy a
        starter from the list, or describe it in the builder box below.</p>
      <div className="cw-row"><Button variant="primary" onClick={newAgent} data-testid="crew-empty-new">+ New agent</Button></div>
    </div>
  );
}

function SaveBar() {
  const isDirty = useCrew(dirty);
  const note = useCrew((s) => s.note);
  const asking = useCrew((s) => s.asking);
  const busy = useCrew((s) => s.busy);
  const open = useCrew((s) => s.open);
  const used = useCrew((s) => s.used);
  const name = useCrew((s) => s.form?.name || "");
  if (asking === "delete")
    return (
      <div className="cw-savebar" data-testid="crew-delete-ask">
        <span className="cw-line">{used.length ? `${name} is used by ${used.join(", ")}: take it out there first.` : `Delete ${name}? Its file goes; nothing else changes.`}</span>
        {!used.length && <Button variant="danger" onClick={() => void remove()} data-testid="crew-delete-yes">Delete it</Button>}
        <Button onClick={() => askDelete(false)} data-testid="crew-delete-no">Keep it</Button>
      </div>
    );
  return (
    <div className="cw-savebar" data-testid="crew-savebar">
      <Button variant="primary" disabled={!isDirty || busy} onClick={() => void save()} data-testid="crew-save">Save</Button>
      <Button disabled={!isDirty} onClick={discard} data-testid="crew-discard">Discard changes</Button>
      <Button onClick={copyOpen} data-testid="crew-copy">Copy</Button>
      {!!open?.name && <Button variant="danger" onClick={() => askDelete(true)} data-testid="crew-delete">Delete...</Button>}
      <span className="cw-line" data-testid="crew-note">{note || (isDirty ? "Not saved yet." : "")}</span>
    </div>
  );
}

export function CrewForm() {
  const a = useCrew((s) => s.form);
  const used = useCrew((s) => s.used);
  const stale = useCrew((s) => s.stale);
  const open = useCrew((s) => s.open);
  const meta = useBuilder((s) => s.meta);
  const est = useTry((s) => s.estimate);
  useEffect(() => {
    if (a) void estimateFor(a.model);
  }, [a?.model]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!a) return <Empty />;
  return (
    <div className="cw-form" data-testid="crew-form" data-name={a.name}>
      {stale && (
        <div className="cw-stale" data-testid="crew-stale">
          <span className="cw-line">The builder changed {open?.name} while you had edits here.</span>
          <Button size="sm" onClick={() => open && void openAgent(open.name, open.scope)}>Reload it (your edits go)</Button>
        </div>
      )}
      <label className="cw-field">
        <span className="cw-label mono">Name</span>
        <input className="input mono" value={a.name} spellCheck={false} data-testid="crew-name"
               onChange={(e) => setForm({ name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 48) })} />
        <span className="cw-line" data-testid="crew-used">{used.length ? `Used by ${used.join(", ")}.` : "Not used yet: no workflow or map names it."}</span>
      </label>
      <label className="cw-field">
        <span className="cw-label mono">What it does</span>
        <TextBox value={a.does} onChange={(e) => setForm({ does: e.target.value })} placeholder="In your words: what it does and what it hands back" data-testid="crew-does" />
      </label>
      <div className="cw-row">
        <Button onClick={() => prefill(`Write the instructions for ${a.name} from what it does`)} disabled={!a.does.trim()} data-testid="crew-write">Write it for me</Button>
        <span className="cw-line">Fills the builder box below; its draft comes back as a preview{meta?.model ? ` (${meta.model}, ${meta.typical})` : ""}. Nothing is saved until you Save.</span>
      </div>
      <label className="cw-field">
        <span className="cw-label mono">The instructions it gets</span>
        <TextBox value={a.instructions || ""} onChange={(e) => setForm({ instructions: e.target.value })} maxRows={16} data-testid="crew-instructions"
                 placeholder={`Empty: it gets "You are ${a.name}. ${a.does}"`} />
      </label>
      <div className="cw-field" data-testid="crew-model">
        <ModelSelect label="MODEL" value={a.model === "auto" ? "" : a.model} inherit={AUTO} testid="crew-model-select" noTest
                     onPick={(ref) => setForm({ model: ref || "auto" })} hint={est?.line ? `About its cost: ${est.line}` : "The model this agent runs on."} />
      </div>
      <Uses a={a} />
      <Careful a={a} />
      <TryIt a={a} />
      <More a={a} />
      <SaveBar />
    </div>
  );
}

export const crewDirty = () => dirty(crew.get());
