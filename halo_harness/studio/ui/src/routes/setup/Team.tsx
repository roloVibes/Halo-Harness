// setup-team (3.3.0.0 R1; 3.6.0.0 R5: the Map step, its block id kept for `halo setup team` and `?block=team`): the
// map new sessions run on -- every map, nearest first (yours, this project's, the starters), `starter` the default
// while no `crew.map` is set; the highlighted row's preview is the map in words (GET setup/team/<name>/preview: main,
// each box, each line's When). Apply writes `crew.map` (POST setup/team {map}, as `halo maps use`). Edit on the Map
// opens it in Agents -> 3 · Map.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { goSection } from "../../lib/store";
import { Button } from "../../lib/ui";
import { openMap } from "../crew/map/mapStore";
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { NONE, pick, shownOf, useSetup, type MapRow } from "./store";

function usePreview(name: string): string[] {
  const [lines, setLines] = useState<string[]>([]);
  const maps = useSetup((s) => s.data?.team.maps);
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
  }, [name, maps]);
  return lines;
}

function Row({ r, on }: { r: MapRow; on: boolean }) {
  return (
    <label className="su-lineup" data-on={on || undefined} data-active={r.active || undefined} data-testid="setup-map" data-name={r.name}>
      <input type="radio" name="setup-map" checked={on} onChange={() => pick("team", r.name)} data-testid="setup-map-input" data-name={r.name} />
      <span className="su-lineup-name">
        {r.label}
        {r.default && <span className="muted"> (default)</span>}
      </span>
      {r.scope && <span className="og-chip mono">{r.scope}</span>}
      {r.active && <span className="og-chip mono su-in-use" data-testid="setup-map-in-use">in use</span>}
      <span className="su-lineup-desc muted">{r.description || `${r.boxes} boxes, ${r.lines} lines`}</span>
    </label>
  );
}

export function TeamDetail() {
  const { ready, error } = useLoadState();
  const rows = useSetup((s) => s.data?.team.maps || NONE);
  const shown = useSetup((s) => shownOf(s, "team"));
  const preview = usePreview(ready ? shown : "");
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block su-team" data-testid="setup-team">
      <p className="su-lead muted">
        The map your sessions run on: who main hands work to, and when. starter (the default) gives main seven agents and lets it pick one per task;
        ship-it hands work along plan, code and review.
      </p>
      <div className="su-team-cols">
        <div className="su-lineups" role="radiogroup" aria-label="Map">
          {rows.map((r) => (
            <Row key={r.name} r={r} on={shown === r.name} />
          ))}
        </div>
        <div className="su-preview">
          <div className="su-group-head mono">
            PREVIEW · {shown}
            <Button size="sm" variant="ghost" onClick={() => (goSection("agents", "map"), void openMap(shown))} title="Open this map in Agents, on 3 · Map"
                    data-testid="setup-edit-map">
              Edit on the Map
            </Button>
          </div>
          <pre className="su-preview-lines mono" data-testid="setup-team-preview">
            {preview.join("\n")}
          </pre>
        </div>
      </div>
      <BlockFoot block="team" label="Apply" what="halo maps use <name>" />
    </div>
  );
}

export function TeamGlance() {
  const active = useSetup((s) => s.data?.team.active || "");
  const source = useSetup((s) => s.data?.team.source || "");
  return (
    <div className="glance">
      <div className="glance-kicker mono">MAP</div>
      <div className="glance-text">{active + (source === "default" ? " (default)" : "")}</div>
      <div className="glance-hint">crew.map in config.json</div>
    </div>
  );
}
