// roles-lineups (3.0.7.0 R2): every lineup, the active one marked, the open
// one highlighted; a click opens it in the editor. New and Duplicate ask for
// a name (a card, never a browser prompt), Delete asks first (shipped ones
// cannot be deleted), Apply makes the open one the lineup new sessions use
// (asks first, showing the role table it writes). Your scope or the
// project's: where New, Save and Delete write.
import { Button, Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { openDialog, roles, scopeLabel, shipped, useRoles } from "./store";
import { openLineup } from "./sync";

export function LineupsDetail() {
  const lineups = useRoles((s) => s.lineups);
  const name = useRoles((s) => s.name);
  const scope = useRoles((s) => s.scope);
  const dirty = useRoles((s) => s.dirty);
  const error = useRoles((s) => s.error);
  const loaded = useRoles((s) => s.loaded);
  const cur = lineups.find((l) => l.name === name);
  if (!loaded) return <div className="og-wait mono muted">reading the lineups...</div>;
  return (
    <div className="rlu" data-testid="roles-lineups-list">
      <div className="rlu-bar">
        <Button size="sm" variant="primary" onClick={() => openDialog({ kind: "new-lineup", from: name || "balanced" })} data-testid="roles-new-lineup">New</Button>
        <Button size="sm" disabled={!name} onClick={() => openDialog({ kind: "dup-lineup", from: name })} data-testid="roles-dup-lineup">Duplicate</Button>
        <Button size="sm" variant="ghost" disabled={!cur || shipped(cur.scope)} onClick={() => openDialog({ kind: "delete-lineup", name })} title={cur && shipped(cur.scope) ? "A shipped lineup cannot be deleted" : "Delete the open lineup (asks first)"} data-testid="roles-delete-lineup">Delete</Button>
        <Button size="sm" disabled={!name || dirty} onClick={() => openDialog({ kind: "apply" })} title={dirty ? "Save first: Apply uses the saved file" : "Make it the lineup new sessions use"}>Apply</Button>
        <span className="spacer" />
        <span className="segmented" role="group" aria-label="Where to write">
          {(["user", "project"] as const).map((sc) => (
            <button key={sc} className={scope === sc ? "on" : ""} aria-pressed={scope === sc} onClick={() => roles.update(() => ({ scope: sc }))}
                    title={sc === "user" ? "~/.halo/teams" : "<project>/.halo/teams"}>{sc}</button>
          ))}
        </span>
      </div>
      {error && <p className="og-problems">{error}</p>}
      {!lineups.length ? (
        <Empty title="No lineup yet" body="New makes one from a shipped lineup." />
      ) : (
        <ul className="rlu-list">
          {lineups.map((l) => (
            <li key={l.name}>
              <button className="ow-row rlu-row" aria-pressed={l.name === name} data-active={l.active || undefined} onClick={() => void openLineup(l.name)} data-testid="roles-lineup" data-name={l.name}>
                <span className="rlu-name">{l.name}</span>
                <span className="rlu-badges">
                  {l.active && <span className="og-chip mono rlu-active" title="new sessions use this lineup">active</span>}
                  <span className="rc-scope mono" data-scope={l.scope}>{scopeLabel(l.scope)}</span>
                </span>
                <span className="rlu-desc muted">{l.description || l.roles.join(", ")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function LineupsGlance() {
  const n = useRoles((s) => s.lineups.length);
  const own = useRoles((s) => s.lineups.filter((l) => !shipped(l.scope)).length);
  const active = useRoles((s) => s.info?.active_team || "");
  const inUse = useRoles((s) => (s.info?.lineup_default ? s.info?.lineup_in_use || "" : "")); // 3.1.9.0 R2: the default
  return (
    <div className="glance">
      <div className="glance-kicker mono">{active ? `ACTIVE · ${active}` : inUse ? `ACTIVE · ${inUse} (default)` : "NO ACTIVE LINEUP"}</div>
      <div className="glance-numbers">
        <Metric value={n} label="lineups" />
        <Metric value={own} label="yours" />
      </div>
    </div>
  );
}
