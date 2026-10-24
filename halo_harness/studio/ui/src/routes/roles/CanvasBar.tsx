// The Roles canvas's toolbar (3.0.7.0 R2): the open lineup with its scope,
// whether it is saved, Save (Mod+S), Undo / Redo (Ctrl+Z, Ctrl+Shift+Z),
// Apply (asks first), Lay out (A), Fit (F) and the zoom. 3.1.6.0 R1: Add tier
// opens a name field on the bar; Enter adds the tier (an empty box appears:
// drag cards in), Escape closes it (tierActions.addTier).
import { useEffect, useRef, type KeyboardEvent } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button } from "../../lib/ui";
import { redo, save, undo } from "./actions";
import { openDialog, roles, scopeLabel, shipped, useRoles } from "./store";
import { addTier } from "./tierActions";

type Props = { zoom: number; setZoom: (z: number) => void; fit: () => void; layout: () => void };

function AddTierField() {
  const ref = useRef<HTMLInputElement>(null);
  const busy = useRoles((s) => s.busy === "save");
  useEffect(() => ref.current?.focus({ preventScroll: true }), []);
  const shut = () => roles.update(() => ({ tierAdd: false }));
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (e.key === "Enter") (e.preventDefault(), void addTier(ref.current?.value || ""));
    else if (e.key === "Escape") (e.preventDefault(), shut());
  };
  return (
    <span className="rc-bar-addtier">
      <input ref={ref} className="input mono rc-bar-tiername" placeholder="tier name, Enter adds it" aria-label="The new tier's name" disabled={busy}
             onKeyDown={onKey} onBlur={(e) => !e.currentTarget.value.trim() && shut()} data-testid="roles-tier-new-name" />
      <Button size="sm" variant="ghost" onClick={shut} aria-label="Close the tier name field">×</Button>
    </span>
  );
}

export function CanvasBar({ zoom, setZoom, fit, layout }: Props) {
  const name = useRoles((s) => s.name);
  const scope = useRoles((s) => s.current?.scope || "");
  const dirty = useRoles((s) => s.dirty);
  const canUndo = useRoles((s) => s.past.length > 0);
  const canRedo = useRoles((s) => s.future.length > 0);
  const busy = useRoles((s) => s.busy);
  const active = useRoles((s) => s.info?.active_team === s.name);
  const byDefault = useRoles((s) => !s.info?.active_team && !!s.info?.lineup_default && s.info?.lineup_in_use === s.name); // 3.1.9.0 R2
  const cards = useRoles((s) => s.graph?.nodes.length || 0);
  const tiers = useRoles((s) => s.graph?.tiers.length || 0);
  const adding = useRoles((s) => s.tierAdd);
  const h = useHelpGroup("lineup_fields");
  return (
    <div className="rc-bar">
      <b className="rc-bar-name">{name}</b>
      <span className="rc-scope mono" data-scope={scope}>{shipped(scope) ? "shipped: saving makes your copy" : scopeLabel(scope)}</span>
      {active && <span className="og-chip mono" data-testid="roles-active">active</span>}
      {byDefault && (
        <span className="og-chip mono" data-testid="roles-active" data-default="1" title="No team: is set, so new sessions run this lineup. Apply another lineup to replace it.">
          active (default)
        </span>
      )}
      <span className="mono muted rc-bar-count">{cards} cards · {tiers} tier{tiers === 1 ? "" : "s"}</span>
      {dirty && <span className="rc-dirty mono" data-testid="roles-dirty">unsaved</span>}
      {adding ? (
        <AddTierField />
      ) : (
        <Button size="sm" variant="ghost" onClick={() => roles.update(() => ({ tierAdd: true }))} title={h["tiers.add"] || "A new tier box: name it, then drag cards in"} data-testid="roles-tier-add">
          Add tier
        </Button>
      )}
      <span className="spacer" />
      <Button size="sm" variant="ghost" disabled={!canUndo} onClick={() => undo()} title="Undo the last edit (Ctrl+Z)" data-testid="roles-undo">Undo</Button>
      <Button size="sm" variant="ghost" disabled={!canRedo} onClick={() => redo()} title="Redo (Ctrl+Shift+Z)">Redo</Button>
      <Button size="sm" variant={dirty ? "primary" : "default"} disabled={!dirty || busy === "save"} onClick={() => void save()} kbd="Mod+S" data-testid="roles-save">Save</Button>
      <Button size="sm" disabled={dirty || busy === "apply"} onClick={() => openDialog({ kind: "apply" })} title={dirty ? "Save first: Apply uses the saved file" : "Make it the lineup new sessions use"} data-testid="roles-apply">Apply</Button>
      <Button size="sm" variant="ghost" onClick={layout} title="Lay the cards out in their tier columns (A)">Lay out</Button>
      <Button size="sm" variant="ghost" onClick={fit} title="Fit the canvas to the panel (F)">Fit</Button>
      <span className="segmented rc-zoom" role="group" aria-label="Zoom">
        <button onClick={() => setZoom(Math.max(0.3, zoom / 1.2))} aria-label="Zoom out">-</button>
        <button onClick={() => setZoom(1)} title="Back to 100%">{Math.round(zoom * 100)}%</button>
        <button onClick={() => setZoom(Math.min(2, zoom * 1.2))} aria-label="Zoom in">+</button>
      </span>
    </div>
  );
}
