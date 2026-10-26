// setup-team (3.3.0.0 R1): the lineup new sessions run -- the wizard's Team
// step as a list: One model for everything, auto (the default while no team:
// is set) and every lineup with its scope; the highlighted row's preview is
// the step's own (GET setup/team/<name>/preview: role -> agent -> model, the
// cost line). Apply writes what the wizard writes (POST setup/team,
// lineup_choice.py): One model = roles off and no team; auto with no team set
// = roles on, nothing else; a lineup = its roles.*, team: <name>, roles on.
// Edit in Roles opens the lineup in the Roles section.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { goSection } from "../../lib/store";
import { Button } from "../../lib/ui";
import { loadLists, openLineup } from "../roles/sync";
import { roles, setView } from "../roles/store";
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { NONE, pick, shownOf, useSetup, type LineupRow } from "./store";

const ONE = "one-model";

function usePreview(name: string): string[] {
  const [lines, setLines] = useState<string[]>([]);
  const lineups = useSetup((s) => s.data?.team.lineups);
  useEffect(() => {
    let live = true;
    if (!name) return;
    api.get<{ lines: string[] }>(`setup/team/${encodeURIComponent(name)}/preview`).then(
      (r) => live && setLines(r.lines || []),
      (e) => live && setLines([`no preview: ${e instanceof Error ? e.message : String(e)}`]),
    );
    return () => {
      live = false;
    };
  }, [name, lineups]);
  return lines;
}

async function editInRoles(name: string): Promise<void> {
  goSection("roles");
  setView("workspace");
  if (!roles.get().loaded) await loadLists();
  if (roles.get().name !== name) await openLineup(name);
}

function Row({ r, on }: { r: LineupRow; on: boolean }) {
  return (
    <label className="su-lineup" data-on={on || undefined} data-active={r.active || undefined} data-testid="setup-lineup" data-name={r.name}>
      <input type="radio" name="setup-lineup" checked={on} onChange={() => pick("team", r.name)} data-testid="setup-lineup-input" data-name={r.name} />
      <span className="su-lineup-name">
        {r.label}
        {r.default && <span className="muted"> (default)</span>}
      </span>
      {r.scope && <span className="og-chip mono">{r.scope}</span>}
      {r.active && <span className="og-chip mono su-in-use" data-testid="setup-lineup-in-use">in use</span>}
      {r.description && <span className="su-lineup-desc muted">{r.description}</span>}
    </label>
  );
}

export function TeamDetail() {
  const { ready, error } = useLoadState();
  const rows = useSetup((s) => s.data?.team.lineups || NONE);
  const shown = useSetup((s) => shownOf(s, "team"));
  const preview = usePreview(ready ? shown : "");
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block su-team" data-testid="setup-team">
      <p className="su-lead muted">
        Which agent, on which model, does each job. auto (the default) hands each sub-task to a model picked for it; One model for everything runs every job on the
        default model.
      </p>
      <div className="su-team-cols">
        <div className="su-lineups" role="radiogroup" aria-label="Lineup">
          {rows.map((r) => (
            <Row key={r.name} r={r} on={shown === r.name} />
          ))}
        </div>
        <div className="su-preview">
          <div className="su-group-head mono">
            PREVIEW · {shown === ONE ? "one model" : shown}
            {shown !== ONE && (
              <Button size="sm" variant="ghost" onClick={() => void editInRoles(shown)} title="Open this lineup in the Roles section" data-testid="setup-edit-in-roles">
                Edit in Roles
              </Button>
            )}
          </div>
          <pre className="su-preview-lines mono" data-testid="setup-team-preview">
            {preview.join("\n")}
          </pre>
        </div>
      </div>
      <BlockFoot block="team" label="Apply" what="halo teams use <name> (One model: halo roles off)" />
    </div>
  );
}

export function TeamGlance() {
  const active = useSetup((s) => s.data?.team.active || "");
  const source = useSetup((s) => s.data?.team.source || "");
  return (
    <div className="glance">
      <div className="glance-kicker mono">TEAM</div>
      <div className="glance-text">{active === ONE ? "one model for everything" : active + (source === "default" ? " (default)" : "")}</div>
      <div className="glance-hint">team and roles.enabled in config.json</div>
    </div>
  );
}
