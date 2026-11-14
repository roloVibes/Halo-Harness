// Agents' workspace (3.3.16.0 R1): `roles` -- Cast and Live, Roles' six panels -- keeps its own layout key, status line
// and panel ids; the shell asks `partPanels` for the panels it draws now, the packs' added. A pack's panel declared for
// an old core section lands here: `agents`, `roles`, and 3.4.0.0 D `orchestra` and `team` (Runs' workspace went with
// the runs fold; packs/studio_rules.py keeps the words). Two optional panels join Live, each closed until a door opens
// it: Activity (the header's "+", the palette) and 3.4.0.0 D the plan review of a goal run that waits on you
// (run/planPanel.ts: "Review the plan" on the run's lead).
import type { AgentsPart } from "../../lib/store";
import type { PanelSpec } from "../../lib/workspace/types";
import { packPanels } from "../packs/registry";
import type { Registry } from "../packs/types";
import { rolesPanels } from "../roles/Roles";
import { activityPanel } from "./fleetPanels";
import { planPanel } from "./run/planPanel";

const BASE: Record<AgentsPart, PanelSpec[]> = { roles: [...rolesPanels, activityPanel, planPanel] };
const ALSO: Record<AgentsPart, string[]> = { roles: ["agents", "orchestra", "team"] };
const cache: Record<AgentsPart, { reg: Registry | null; specs: PanelSpec[] }> = { roles: { reg: null, specs: BASE.roles } };

/** The part's panels: its own, then the ones packs add to it (the same array while the registry is the same). */
export function partPanels(reg: Registry, part: AgentsPart): PanelSpec[] {
  const c = cache[part];
  if (c.reg !== reg) {
    const extra = [...packPanels(reg, part), ...ALSO[part].flatMap((w) => packPanels(reg, w))];
    cache[part] = { reg, specs: extra.length ? [...BASE[part], ...extra] : BASE[part] };
  }
  return cache[part].specs;
}
