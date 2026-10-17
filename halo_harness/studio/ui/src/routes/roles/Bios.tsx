// roles-bios (3.0.7.0 R2): every agent bio (its scope, kind and model); a
// click opens it in the form below (BioForm), a drag onto the canvas adds it
// to the lineup. New and Duplicate ask for a name on a card, Delete asks
// first (shipped bios stay).
import { Button } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { BioForm } from "./BioForm";
import { openBio } from "./bioActions";
import { openDialog, scopeLabel, shipped, useRoles } from "./store";

export function BiosDetail() {
  const bios = useRoles((s) => s.bios);
  const cur = useRoles((s) => s.bio);
  const scope = useRoles((s) => s.bioData?.scope);
  return (
    <div className="rbs" data-testid="roles-bios-body">
      <div className="rlu-bar">
        <Button size="sm" variant="primary" onClick={() => openDialog({ kind: "new-bio", from: cur || "general" })} data-testid="roles-new-bio">New</Button>
        <Button size="sm" disabled={!cur} onClick={() => openDialog({ kind: "dup-bio", from: cur })} data-testid="roles-dup-bio">Duplicate</Button>
        <Button size="sm" variant="ghost" disabled={!cur || shipped(scope)} onClick={() => openDialog({ kind: "delete-bio", name: cur })}>Delete</Button>
      </div>
      <ul className="rbs-list" aria-label="Agent bios">
        {bios.map((b) => (
          <li key={b.name}>
            <button className="ow-row rbs-row" aria-pressed={b.name === cur} onClick={() => void openBio(b.name)} draggable
                    onDragStart={(e) => (e.dataTransfer.setData("text/halo-bio", b.name), e.dataTransfer.setData("text/plain", b.name), (e.dataTransfer.effectAllowed = "copy"))}
                    data-testid="roles-bio" data-name={b.name} title={b.description || "drag onto the canvas to add it"}>
              <span className="rlu-name">{b.name}</span>
              <span className="rlu-badges"><span className="rc-scope mono" data-scope={b.scope}>{scopeLabel(b.scope)}</span></span>
              <span className="rlu-desc muted mono">{b.kind || "?"} · {b.model || "no model"}</span>
            </button>
          </li>
        ))}
      </ul>
      <BioForm />
    </div>
  );
}

export function BiosGlance() {
  const n = useRoles((s) => s.bios.length);
  const own = useRoles((s) => s.bios.filter((b) => !shipped(b.scope)).length);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={n} label="bios" />
        <Metric value={own} label="yours" />
      </div>
      <div className="glance-hint">Expand to edit one, or drag one onto the canvas.</div>
    </div>
  );
}
