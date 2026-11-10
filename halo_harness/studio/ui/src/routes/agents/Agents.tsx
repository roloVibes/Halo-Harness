// Agents (Alt+2, 3.3.16.0 R1 "Agents: one section"): Team, Roles and Orchestra folded into one section with three
// views, the switch first on its bar (ViewSwitch.tsx):
//   Cast  the lineup and its bios -- Roles as it was: its Start view until you have a lineup of your own, then the
//         canvas with its tiers, Lineups, Bios, the Inspector (Assignment / Lineup), Problems, Models.
//   Runs  Orchestra as it was: the goal form (its Start view), the plan canvas, the lanes, the report, the saved
//         workflows; each lane says what it owns (runs/Owns.tsx, the claim ledger's keys), and Test this lineup is on
//         the bar (runs/TestLineup.tsx). Team's board went: a run's plan shows who owns what.
//   Live  Roles Live: the session's agents as a tree, an Orchestra run's lanes under its lead; 3.3.16.0 R2 the fleet
//         scope: every machine, its sessions, their agents (the Fleet section folded in: routes/agents/live/).
// 3.3.16.0 R2: the fleet's Attention queue floats over every view (AttentionChip.tsx, closed on load, A toggles it).
// It opens on Cast with nothing else open. A view's workspace mounts the first time it shows and stays mounted (its
// state kept), as the shell keeps a visited section. The Workflows board of 3.3.16.0 R3 is meant to sit beside these
// as a fourth view on the same switch.
import { useEffect, useState } from "react";
import type { PanelSpec } from "../../lib/workspace/types";
import { OrchestraView } from "../orchestra/Start";
import { usePacks } from "../packs/store";
import { RolesView } from "../roles/Start";
import { useAgentsKeys } from "./keys";
import { partPanels } from "./parts";
import { useAgentsView } from "./store";
import { AgentsBar } from "./ViewSwitch";
import { AttentionPanel } from "./AttentionChip";
import { useAttentionKey } from "./attention";

export function AgentsView(_props: { section: string; specs: PanelSpec[] }) {
  const view = useAgentsView();
  const reg = usePacks((s) => s.reg);
  const runs = view === "runs";
  const [seen, setSeen] = useState({ roles: !runs, orchestra: runs });
  useEffect(() => setSeen((s) => (runs ? (s.orchestra ? s : { ...s, orchestra: true }) : s.roles ? s : { ...s, roles: true })), [runs]);
  useAgentsKeys();
  useAttentionKey();
  return (
    <div className="ag" data-testid="agents" data-view={view}>
      <AgentsBar view={view} />
      <div className="ag-body">
        {seen.roles && (
          <div className="ag-part" hidden={runs} data-part="roles">
            <RolesView section="roles" specs={partPanels(reg, "roles")} />
          </div>
        )}
        {seen.orchestra && (
          <div className="ag-part" hidden={!runs} data-part="orchestra">
            <OrchestraView section="orchestra" specs={partPanels(reg, "orchestra")} />
          </div>
        )}
        <AttentionPanel />
      </div>
    </div>
  );
}
