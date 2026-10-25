// roles-bios (3.0.7.0 R2): every agent bio (its scope, kind and model); a
// click opens it in the form below (BioForm), a drag onto the canvas adds it
// to the lineup. New and Duplicate ask for a name on a card, Delete asks
// first (shipped bios stay). 3.2.0.0 R2: grouped by source (SourceGroups.tsx:
// yours, project, one box per pack, shipped); a pack's bio has Preview (the
// form, read-only), Clone and Customize, and shows the tags it asks for.
// 3.2.2.0 R6: over the form, "<name> changed on disk" (Reload / Keep mine) or "deleted on disk" (DiskNote.tsx).
import { Button } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { BioForm } from "./BioForm";
import { BioDiskNote } from "./DiskNote";
import { openBio } from "./bioActions";
import { cloneFromPack } from "./packActions";
import { groupBySource, SourceBox } from "./SourceGroups";
import { openDialog, packOf, readOnlySource, scopeLabel, useRoles } from "./store";
import type { BioRow } from "./types";

function Row({ b, open }: { b: BioRow; open: boolean }) {
  const pack = packOf(b.scope);
  const tags = (b.capabilities || []).join(", ");
  return (
    <li className={pack ? "rlu-pack" : undefined}>
      <button className="ow-row rbs-row" aria-pressed={open} onClick={() => void openBio(b.name)} draggable
              onDragStart={(e) => (e.dataTransfer.setData("text/halo-bio", b.name), e.dataTransfer.setData("text/plain", b.name), (e.dataTransfer.effectAllowed = "copy"))}
              data-testid="roles-bio" data-name={b.name} title={b.model_problem || b.description || "drag onto the canvas to add it"}>
        <span className="rlu-name">{b.name}</span>
        <span className="rlu-badges">
          {b.shadows && <span className="og-chip mono" data-testid="roles-shadows" title={`Your file has the name pack ${b.shadows} offers: yours is the one used`}>shadows pack {b.shadows}</span>}
          {b.from_pack && <span className="og-chip mono" title="Cloned from this pack">from {b.from_pack}</span>}
          <span className="rc-scope mono" data-scope={b.scope}>{scopeLabel(b.scope)}</span>
        </span>
        <span className="rlu-desc muted mono">{b.kind || "?"} · {b.model || "no model"}{tags ? ` · needs ${tags}` : ""}{b.model_problem ? " (none in the catalog)" : ""}</span>
      </button>
      {pack && (
        <span className="rlu-acts" data-testid="roles-pack-actions">
          <Button size="sm" variant="ghost" onClick={() => void openBio(b.name)} title="Open it in the form below, read-only" data-testid="roles-pack-preview">Preview</Button>
          <Button size="sm" variant="ghost" onClick={() => void cloneFromPack("bio", b.name, false)} title="Copy it into your bios (asks first if one has the name)" data-testid="roles-pack-clone">Clone</Button>
          <Button size="sm" variant="ghost" onClick={() => void cloneFromPack("bio", b.name, true)} title="Clone it and open your copy to edit" data-testid="roles-pack-customize">Customize</Button>
        </span>
      )}
    </li>
  );
}

export function BiosDetail() {
  const bios = useRoles((s) => s.bios);
  const packs = useRoles((s) => s.info?.packs);
  const cur = useRoles((s) => s.bio);
  const scope = useRoles((s) => s.bioData?.scope);
  return (
    <div className="rbs" data-testid="roles-bios-body">
      <div className="rlu-bar">
        <Button size="sm" variant="primary" onClick={() => openDialog({ kind: "new-bio", from: cur || "general" })} data-testid="roles-new-bio">New</Button>
        <Button size="sm" disabled={!cur} onClick={() => openDialog({ kind: "dup-bio", from: cur })} data-testid="roles-dup-bio">Duplicate</Button>
        <Button size="sm" variant="ghost" disabled={!cur || readOnlySource(scope)} onClick={() => openDialog({ kind: "delete-bio", name: cur })}>Delete</Button>
      </div>
      <div className="rbs-groups" aria-label="Agent bios">
        {groupBySource(bios, packs).map((g) => (
          <SourceBox key={g.key} group={g} what="bio">
            <ul className="rbs-list">{g.rows.map((b) => <Row key={b.name} b={b} open={b.name === cur} />)}</ul>
          </SourceBox>
        ))}
      </div>
      <BioDiskNote />
      <BioForm />
    </div>
  );
}

export function BiosGlance() {
  const n = useRoles((s) => s.bios.length);
  const own = useRoles((s) => s.bios.filter((b) => !readOnlySource(b.scope)).length);
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
