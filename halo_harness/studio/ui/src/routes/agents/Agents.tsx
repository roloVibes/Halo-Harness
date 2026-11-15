// Agents (Alt+2): three tabs and nothing else (3.6.0.0 R5, the v3 design) -- 1 · Agents (make an agent: routes/crew/),
// 2 · Workflows (your agents in steps: routes/crew/flows/), 3 · Map (who main hands work to and when; lit while a
// session runs, History replays on it: routes/crew/map/). Each tab draws the switch in its own view bar (ViewSwitch.tsx).
// The Attention queue floats over every tab (AttentionChip.tsx, closed on load, A toggles it). A tab mounts the first
// time it shows and stays mounted (its state kept), as the shell keeps a visited section.
import { useEffect, useState } from "react";
import type { PanelSpec } from "../../lib/workspace/types";
import { useAgentsKeys } from "./keys";
import { useAgentsView } from "./store";
import { AttentionPanel } from "./AttentionChip";
import { useAttentionKey } from "./attention";
import { CrewView } from "../crew/Crew";
import { FlowsView } from "../crew/flows/Flows";
import { MapView } from "../crew/map/MapView";

export function AgentsView(_props: { section: string; specs: PanelSpec[] }) {
  const view = useAgentsView();
  const [seen, setSeen] = useState({ crew: view === "crew", workflows: view === "workflows", map: view === "map" });
  useEffect(() => setSeen((s) => (s[view] ? s : { ...s, [view]: true })), [view]);
  useAgentsKeys();
  useAttentionKey();
  return (
    <div className="ag" data-testid="agents" data-view={view}>
      <div className="ag-body">
        {seen.crew && (
          <div className="ag-part" hidden={view !== "crew"} data-part="crew">
            <CrewView />
          </div>
        )}
        {seen.workflows && (
          <div className="ag-part" hidden={view !== "workflows"} data-part="workflows">
            <FlowsView />
          </div>
        )}
        {seen.map && (
          <div className="ag-part" hidden={view !== "map"} data-part="map">
            <MapView />
          </div>
        )}
        <AttentionPanel />
      </div>
    </div>
  );
}
