// Agents (Alt+2): four tabs and nothing else (3.6.0.0 R5, 3.6.0.2 R52) -- 1 · Agents (make an agent: routes/crew/),
// 2 · Workflows (your agents in steps: routes/crew/flows/), 3 · Map (the plan: who main hands work to and when, and the
// goal runs' pages in its drawer: routes/crew/map/), 4 · Live (what a session is doing now, drawn on the map it really follows:
// LiveView.tsx). Each tab draws the switch in its own view bar (ViewSwitch.tsx).
// The Attention queue floats over every tab (AttentionChip.tsx, closed on load, A toggles it). A tab mounts the first
// time it shows and stays mounted (its state kept), as the shell keeps a visited section. A page that boots on Agents with
// no `view=` draws the tab bar and one quiet line, no view, until the session list has been read (store.ts `waiting`).
import { useEffect, useState } from "react";
import type { PanelSpec } from "../../lib/workspace/types";
import { useAgentsKeys } from "./keys";
import { agents, useAgentsView } from "./store";
import { useStore } from "../../lib/store";
import { READING_SESSIONS } from "../../lib/agentsDoor";
import { ViewSwitch } from "./ViewSwitch";
import { AttentionChip, AttentionPanel } from "./AttentionChip";
import { useAttentionKey } from "./attention";
import { CrewView } from "../crew/Crew";
import { FlowsView } from "../crew/flows/Flows";
import { MapView } from "../crew/map/MapView";
import { LiveView } from "./LiveView";
import { startLive } from "../shared/liveFeed";

export function AgentsView(_props: { section: string; specs: PanelSpec[] }) {
  const shown = useAgentsView();
  const waiting = useStore(agents, (s) => s.waiting);
  const view = waiting ? "" : shown;
  const [seen, setSeen] = useState({ crew: view === "crew", workflows: view === "workflows", map: view === "map", live: view === "live" });
  useEffect(() => setSeen((s) => (!view || s[view] ? s : { ...s, [view]: true })), [view]);
  // P4 batch 12: the Feed's lines are collected from the section's first draw, so an ask said while he was on another
  // tab is in 4 · Live's Feed when a door opens it there (startLive runs once per page)
  useEffect(() => startLive(), []);
  useAgentsKeys();
  useAttentionKey();
  return (
    <div className="ag" data-testid="agents" data-view={view} data-reading={waiting ? "1" : undefined}>
      <div className="ag-body">
        {waiting && (
          <div className="cw" data-testid="agents-reading">
            <div className="viewbar" role="toolbar" aria-label="Agents">
              <span className="cw-lead"><ViewSwitch view="" /><AttentionChip /></span>
            </div>
            <div className="ag-reading muted mono" data-testid="agents-reading-line">{READING_SESSIONS}</div>
          </div>
        )}
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
        {seen.live && (
          <div className="ag-part" hidden={view !== "live"} data-part="live">
            <LiveView />
          </div>
        )}
        <AttentionPanel />
      </div>
    </div>
  );
}
