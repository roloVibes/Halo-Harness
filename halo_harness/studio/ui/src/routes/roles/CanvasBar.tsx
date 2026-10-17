// The Roles canvas's toolbar (3.0.7.0 R2): the open lineup with its scope,
// whether it is saved, Save (Mod+S), Undo / Redo (Ctrl+Z, Ctrl+Shift+Z),
// Apply (asks first), Lay out (A), Fit (F) and the zoom.
import { Button } from "../../lib/ui";
import { redo, save, undo } from "./actions";
import { openDialog, scopeLabel, shipped, useRoles } from "./store";

type Props = { zoom: number; setZoom: (z: number) => void; fit: () => void; layout: () => void };

export function CanvasBar({ zoom, setZoom, fit, layout }: Props) {
  const name = useRoles((s) => s.name);
  const scope = useRoles((s) => s.current?.scope || "");
  const dirty = useRoles((s) => s.dirty);
  const canUndo = useRoles((s) => s.past.length > 0);
  const canRedo = useRoles((s) => s.future.length > 0);
  const busy = useRoles((s) => s.busy);
  const active = useRoles((s) => s.info?.active_team === s.name);
  const cards = useRoles((s) => s.graph?.nodes.length || 0);
  const tiers = useRoles((s) => s.graph?.tiers.length || 0);
  return (
    <div className="rc-bar">
      <b className="rc-bar-name">{name}</b>
      <span className="rc-scope mono" data-scope={scope}>{shipped(scope) ? "shipped: saving makes your copy" : scopeLabel(scope)}</span>
      {active && <span className="og-chip mono" data-testid="roles-active">active</span>}
      <span className="mono muted rc-bar-count">{cards} cards · {tiers} tier{tiers === 1 ? "" : "s"}</span>
      {dirty && <span className="rc-dirty mono" data-testid="roles-dirty">unsaved</span>}
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
