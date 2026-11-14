// Agents (Alt+2, 3.3.16.0 R1 "Agents: one section"): Team, Roles and Orchestra folded into one section, the view switch
// first on its bar (ViewSwitch.tsx):
//   Cast       the lineup and its bios -- Roles as it was: its Start view until you have a lineup of your own, then
//              the canvas with its tiers, Lineups, Bios, the Inspector (Assignment / Lineup), Problems, Models.
//   Live       what runs now (3.3.18.0 "The living canvas"): the session's agents as a tree, a goal run as a job on it
//              (3.4.0.0 D: its lead and lanes under the run's block, routes/agents/run/), every machine on the fleet
//              scope; History (the bar) holds what ran, a finished run's report included.
//   Workflows  the board of squares main may hand work to, with its library (routes/agents/workflows/Board.tsx).
// 3.3.16.0 R2: the fleet's Attention queue floats over every view (AttentionChip.tsx, closed on load, A toggles it).
// 3.6.0.0 R1: it opens on 1 · Agents (routes/crew/; a bare ?mode=agents door keeps Live) with nothing else open. A view's workspace mounts the first time it shows and stays mounted (its
// state kept), as the shell keeps a visited section. 3.4.0.0 D "the runs fold": the Runs view, its Start screen and its
// workspace are gone; "Run a goal" on Live's bar opens the goal form as a panel (run/GoalDrawer.tsx).
import { useEffect, useState } from "react";
import type { PanelSpec } from "../../lib/workspace/types";
import { usePacks } from "../packs/store";
import { RolesView } from "../roles/Start";
import { useAgentsKeys } from "./keys";
import { partPanels } from "./parts";
import { useAgentsView } from "./store";
import { AgentsBar } from "./ViewSwitch";
import { AttentionPanel } from "./AttentionChip";
import { useAttentionKey } from "./attention";
import { Board } from "./workflows/Board";
import { CrewView } from "../crew/Crew"; // 3.6.0.0 R1: 1 · Agents
import { FlowsView } from "../crew/flows/Flows"; // 3.6.0.0 R2: 2 · Workflows
import { DragGhost } from "./blocks/BlockOverlay"; // 3.3.16.3: the label under the pointer while a block drag moves

export function AgentsView(_props: { section: string; specs: PanelSpec[] }) {
  const view = useAgentsView();
  const reg = usePacks((s) => s.reg);
  const board = view === "workflows";
  const crew = view === "crew"; // 3.6.0.0 R1: the Agents tab (routes/crew/), its own view bar
  const flows = view === "flows"; // 3.6.0.0 R2: the Workflows tab (routes/crew/flows/), its own view bar
  const part = crew ? "crew" : flows ? "flows" : board ? "board" : "roles";
  const [seen, setSeen] = useState({ roles: part === "roles", board, crew, flows });
  useEffect(() => setSeen((s) => (s[part] ? s : { ...s, [part]: true })), [part]);
  useAgentsKeys();
  useAttentionKey();
  return (
    <div className="ag" data-testid="agents" data-view={view}>
      {!crew && !flows && <AgentsBar view={view} />}
      <div className="ag-body">
        {seen.crew && (
          <div className="ag-part" hidden={!crew} data-part="crew">
            <CrewView />
          </div>
        )}
        {seen.flows && (
          <div className="ag-part" hidden={!flows} data-part="flows">
            <FlowsView />
          </div>
        )}
        {seen.roles && (
          <div className="ag-part" hidden={board || crew || flows} data-part="roles">
            <RolesView section="roles" specs={partPanels(reg, "roles")} />
          </div>
        )}
        {seen.board && (
          <div className="ag-part" hidden={!board} data-part="workflows">
            <Board />
          </div>
        )}
        <AttentionPanel />
        <DragGhost />
      </div>
    </div>
  );
}
