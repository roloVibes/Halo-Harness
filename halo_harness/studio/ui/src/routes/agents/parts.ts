// Agents' two workspaces (3.3.16.0 R1): `roles` (Cast and Live: Roles' six panels) and `orchestra` (Runs: Orchestra's
// eight). Each keeps its own layout key, status line and panel ids; the shell asks `partPanels` for the panels the
// part draws now, the packs' added. A pack's panel declared for an old core section lands on the part that took it in:
// `agents` and `roles` on Cast, `orchestra` and `team` on Runs (packs/studio_rules.py keeps the words); 3.3.16.0 R2:
// `fleet` on Cast and Live (the roles workspace), where a machine's agents are now.
import type { AgentsPart } from "../../lib/store";
import type { PanelSpec } from "../../lib/workspace/types";
import { orchestraPanels } from "../orchestra/Orchestra";
import { packPanels } from "../packs/registry";
import type { Registry } from "../packs/types";
import { rolesPanels } from "../roles/Roles";
import { activityPanel, missionPanel } from "./fleetPanels";

// 3.3.16.0 R2: Live takes Fleet's Activity, Runs its Mission (fleetPanels.ts), each optional
const BASE: Record<AgentsPart, PanelSpec[]> = { roles: [...rolesPanels, activityPanel], orchestra: [...orchestraPanels, missionPanel] };
const ALSO: Record<AgentsPart, string[]> = { roles: ["agents", "fleet"], orchestra: ["team"] }; // R2: a pack's Fleet panel lands on Live
const cache: Record<AgentsPart, { reg: Registry | null; specs: PanelSpec[] }> = {
  roles: { reg: null, specs: BASE.roles },
  orchestra: { reg: null, specs: BASE.orchestra },
};

/** The part's panels: its own, then the ones packs add to it (the same array while the registry is the same). */
export function partPanels(reg: Registry, part: AgentsPart): PanelSpec[] {
  const c = cache[part];
  if (c.reg !== reg) {
    const extra = [...packPanels(reg, part), ...ALSO[part].flatMap((w) => packPanels(reg, w))];
    cache[part] = { reg, specs: extra.length ? [...BASE[part], ...extra] : BASE[part] };
  }
  return cache[part].specs;
}
