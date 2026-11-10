// Agents' two workspaces (3.3.16.0 R1): `roles` (Cast and Live: Roles' six panels) and `orchestra` (Runs: Orchestra's
// eight). Each keeps its own layout key, status line and panel ids; the shell asks `partPanels` for the panels the
// part draws now, the packs' added. A pack's panel declared for an old core section lands on the part that took it in:
// `agents` and `roles` on Cast, `orchestra` and `team` on Runs (packs/studio_rules.py keeps the words).
import type { AgentsPart } from "../../lib/store";
import type { PanelSpec } from "../../lib/workspace/types";
import { orchestraPanels } from "../orchestra/Orchestra";
import { packPanels } from "../packs/registry";
import type { Registry } from "../packs/types";
import { rolesPanels } from "../roles/Roles";

const BASE: Record<AgentsPart, PanelSpec[]> = { roles: rolesPanels, orchestra: orchestraPanels };
const ALSO: Record<AgentsPart, string> = { roles: "agents", orchestra: "team" };
const cache: Record<AgentsPart, { reg: Registry | null; specs: PanelSpec[] }> = {
  roles: { reg: null, specs: rolesPanels },
  orchestra: { reg: null, specs: orchestraPanels },
};

/** The part's panels: its own, then the ones packs add to it (the same array while the registry is the same). */
export function partPanels(reg: Registry, part: AgentsPart): PanelSpec[] {
  const c = cache[part];
  if (c.reg !== reg) {
    const extra = [...packPanels(reg, part), ...packPanels(reg, ALSO[part])];
    cache[part] = { reg, specs: extra.length ? [...BASE[part], ...extra] : BASE[part] };
  }
  return cache[part].specs;
}
