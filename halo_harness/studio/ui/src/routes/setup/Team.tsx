// setup-team (3.3.0.0 R1; 3.6.0.0 R5: the Map step, its block id kept for `halo setup team` and `?block=team`): the
// map new sessions run on -- 3.6.0.5 A8: "Auto (the default)" first, his maps, this project's, "{name} (ships with
// Halo)", One model for everything (`one-model`: roles off, no map) last (studio/setup_state.py map_rows); the
// highlighted row's preview is the map in words (GET setup/team/<name>/preview: main, each box, each line's When).
// Apply writes `crew.map` (POST setup/team {map}, as `halo maps use`); Apply on Auto unsets it. Edit on the Map opens
// it in Agents -> 3 · Map (not on Auto: no plan to edit). A5: his old file's row (OldRow) opens and copies only.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { goSection } from "../../lib/store";
import { Button } from "../../lib/ui";
import { openMap } from "../crew/map/mapStore";
import { copyName, copyOld } from "../crew/map/oldCopy";
import { DEFAULT_MAP, isAuto } from "../crew/map/truthWords";
import { mapWord } from "./words";
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { NONE, pick, shownOf, useSetup, type MapRow } from "./store";

const ONE_MODEL = "one-model";

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

/** 3.6.0.5 A8: a scope chip only where it tells something -- this project's map, a pack's; none for his own or Auto. */
const CHIP: Record<string, string> = { project: "this project's", pack: "pack" };

/** A5: his own old file named auto or starter -- no radio (it cannot be applied); its name opens it read-only on the Map
 *  by its scope; its one button copies it as my-map. Nothing else on that row. */
function OldRow({ r, names }: { r: MapRow; names: string[] }) {
  return (
    <div className="su-lineup" data-testid="setup-map" data-name={r.name} data-old="1">
      <button type="button" className="su-lineup-name mp-link" data-testid="setup-map-old" title="Open it on the Map (read-only)"
              onClick={() => (void openMap(r.name, r.scope), goSection("agents", "map"))}>{r.label}</button>
      <Button size="sm" data-testid="map-old-copy" onClick={() => void copyOld(r.name, r.scope)}>Copy as {copyName(names)}</Button>
    </div>
  );
}

function Row({ r, on }: { r: MapRow; on: boolean }) {
  return (
    <label className="su-lineup" data-on={on || undefined} data-active={r.active || undefined} data-testid="setup-map" data-name={r.name}>
      <input type="radio" name="setup-map" checked={on} onChange={() => pick("team", r.name)} data-testid="setup-map-input" data-name={r.name} />
      <span className="su-lineup-name">{r.label}</span>
      {CHIP[r.scope] && <span className="og-chip mono">{CHIP[r.scope]}</span>}
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
  const names = rows.map((r) => r.name);
  const head = shown === ONE_MODEL ? "One model for everything" : isAuto(shown) ? DEFAULT_MAP : shown;
  return (
    <div className="su-block su-team" data-testid="setup-team">
      <p className="su-lead muted">
        Auto (the default): main picks who works on each task, and a model for each one. A map of yours: main hands work along its lines.
        One model for everything: every job on your model, with no map.
      </p>
      <div className="su-team-cols">
        <div className="su-lineups" role="radiogroup" aria-label="Map">
          {rows.map((r) => (r.old ? <OldRow key={`${r.scope}:${r.name}`} r={r} names={names} />
            : <Row key={`${r.scope}:${r.name}`} r={r} on={shown === r.name} />))}
        </div>
        <div className="su-preview">
          <div className="su-group-head mono">
            PREVIEW · {head}
            {/* A11: Auto has no plan to edit -- no Edit on the Map */}
            {shown !== ONE_MODEL && !isAuto(shown) && (
              <Button size="sm" variant="ghost" onClick={() => (goSection("agents", "map"), void openMap(shown))} title="Open this map in Agents, on 3 · Map"
                      data-testid="setup-edit-map">
                Edit on the Map
              </Button>
            )}
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
  const team = useSetup((s) => s.data?.team);
  const active = team?.active || "";
  return (
    <div className="glance">
      <div className="glance-kicker mono">MAP</div>
      <div className="glance-text">{active === ONE_MODEL ? "One model for everything" : team ? mapWord({ team }) : ""}</div>
      <div className="glance-hint">crew.map in config.json</div>
    </div>
  );
}
