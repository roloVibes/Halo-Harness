// roles-lineups (3.0.7.0 R2): every lineup, the active one marked, the open
// one highlighted; a click opens it in the editor. New and Duplicate ask for
// a name (a card, never a browser prompt), Delete asks first (shipped ones
// cannot be deleted), Apply makes the open one the lineup new sessions use
// (asks first, showing the role table it writes). Your scope or the
// project's: where New, Save and Delete write. 3.2.0.0 R2: grouped by source
// (SourceGroups.tsx: yours, project, one box per pack, shipped); a pack's row
// has Preview (read-only on the canvas), Clone, Customize and Apply.
import { Button, Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { applyFromPack, cloneFromPack } from "./packActions";
import { groupBySource, SourceBox } from "./SourceGroups";
import { openDialog, packOf, readOnlySource, roles, scopeLabel, useRoles } from "./store";
import { openLineup } from "./sync";
import type { LineupRow } from "./types";
import { LineupDiskNote } from "./DiskNote";

function Row({ l, open }: { l: LineupRow; open: boolean }) {
  const pack = packOf(l.scope);
  return (
    <li className={pack ? "rlu-pack" : undefined}>
      <button className="ow-row rlu-row" aria-pressed={open} data-active={l.active || undefined} onClick={() => void openLineup(l.name)} data-testid="roles-lineup" data-name={l.name}
              title={pack ? `From pack ${pack}, read-only: Preview opens it on the canvas` : undefined}>
        <span className="rlu-name">{l.name}</span>
        <span className="rlu-badges">
          {l.active && <span className="og-chip mono rlu-active" title="new sessions use this lineup">active</span>}
          {l.shadows && <span className="og-chip mono" data-testid="roles-shadows" title={`Your file has the name pack ${l.shadows} offers: yours is the one used`}>shadows pack {l.shadows}</span>}
          {l.from_pack && <span className="og-chip mono" title="Cloned from this pack">from {l.from_pack}</span>}
          <span className="rc-scope mono" data-scope={l.scope}>{scopeLabel(l.scope)}</span>
        </span>
        <span className="rlu-desc muted">{l.description || l.roles.join(", ")}</span>
      </button>
      {pack && (
        <span className="rlu-acts" data-testid="roles-pack-actions">
          <Button size="sm" variant="ghost" onClick={() => void openLineup(l.name)} title="Open it on the canvas, read-only" data-testid="roles-pack-preview">Preview</Button>
          <Button size="sm" variant="ghost" onClick={() => void cloneFromPack("lineup", l.name, false)} title="Copy it into your lineups (asks first if yours has the name)" data-testid="roles-pack-clone">Clone</Button>
          <Button size="sm" variant="ghost" onClick={() => void cloneFromPack("lineup", l.name, true)} title="Clone it and open your copy to edit" data-testid="roles-pack-customize">Customize</Button>
          <Button size="sm" onClick={() => void applyFromPack(l.name)} title="Make it the lineup new sessions use (asks first)" data-testid="roles-pack-apply">Apply</Button>
        </span>
      )}
    </li>
  );
}

export function LineupsDetail() {
  const lineups = useRoles((s) => s.lineups);
  const packs = useRoles((s) => s.info?.packs);
  const name = useRoles((s) => s.name);
  const scope = useRoles((s) => s.scope);
  const dirty = useRoles((s) => s.dirty);
  const error = useRoles((s) => s.error);
  const loaded = useRoles((s) => s.loaded);
  const cur = lineups.find((l) => l.name === name);
  if (!loaded) return null; // 3.3.2.0 R3: the section's own wait says it while it reads (RolesView)
  return (
    <div className="rlu" data-testid="roles-lineups-list">
      <div className="rlu-bar">
        <Button size="sm" variant="primary" onClick={() => openDialog({ kind: "new-lineup", from: name || "balanced" })} data-testid="roles-new-lineup">New</Button>
        <Button size="sm" disabled={!name} onClick={() => openDialog({ kind: "dup-lineup", from: name })} data-testid="roles-dup-lineup">Duplicate</Button>
        <Button size="sm" variant="ghost" disabled={!cur || readOnlySource(cur.scope)} onClick={() => openDialog({ kind: "delete-lineup", name })} title={cur && readOnlySource(cur.scope) ? `A ${scopeLabel(cur.scope)} lineup cannot be deleted` : "Delete the open lineup (asks first)"} data-testid="roles-delete-lineup">Delete</Button>
        <Button size="sm" disabled={!name || dirty} onClick={() => openDialog({ kind: "apply" })} title={dirty ? "Save first: Apply uses the saved file" : "Make it the lineup new sessions use"}>Apply</Button>
        <span className="spacer" />
        <span className="segmented" role="group" aria-label="Where to write">
          {(["user", "project"] as const).map((sc) => (
            <button key={sc} className={scope === sc ? "on" : ""} aria-pressed={scope === sc} onClick={() => roles.update(() => ({ scope: sc }))}
                    title={sc === "user" ? "~/.halo/teams" : "<project>/.halo/teams"}>{sc}</button>
          ))}
        </span>
      </div>
      <LineupDiskNote list />
      {error && <p className="og-problems">{error}</p>}
      {!lineups.length ? (
        <Empty title="No lineup yet" body="New makes one from a shipped lineup." />
      ) : (
        groupBySource(lineups, packs).map((g) => (
          <SourceBox key={g.key} group={g} what="lineup">
            <ul className="rlu-list">{g.rows.map((l) => <Row key={l.name} l={l} open={l.name === name} />)}</ul>
          </SourceBox>
        ))
      )}
    </div>
  );
}

export function LineupsGlance() {
  const n = useRoles((s) => s.lineups.length);
  const own = useRoles((s) => s.lineups.filter((l) => !readOnlySource(l.scope)).length);
  const packs = useRoles((s) => s.info?.packs?.length || 0);
  const active = useRoles((s) => s.info?.active_team || "");
  const inUse = useRoles((s) => (s.info?.lineup_default ? s.info?.lineup_in_use || "" : "")); // 3.1.9.0 R2: the default
  return (
    <div className="glance">
      <div className="glance-kicker mono">{active ? `ACTIVE · ${active}` : inUse ? `ACTIVE · ${inUse} (default)` : "NO ACTIVE LINEUP"}</div>
      <div className="glance-numbers">
        <Metric value={n} label="lineups" />
        <Metric value={own} label="yours" />
        {packs > 0 && <Metric value={packs} label={packs === 1 ? "pack" : "packs"} />}
      </div>
    </div>
  );
}
