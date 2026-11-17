// The plan review of a goal run (3.0.9.0 R2's plan canvas; 3.6.0.0 R5: an optional panel of the Map's workspace, Live's
// before). A run started with "Review the plan first" stops after the lead's split and waits on you: its pages in the
// Map's drawer say so and carry "Review the plan", which opens this panel (as do the palette's "Agents: review the plan"
// and the supervisor's "open the plan"). Nothing opens it on its own. Approve and run hands the plan to the waiting run
// and the panel closes; Reject does the same.
import type { PanelSpec } from "../../../lib/workspace/types";
import { goSection } from "../../../lib/store";
import { hidePanel, layoutStore, showPanel } from "../../../lib/workspace/persist";
import { planPanels } from "../../orchestra/plan/PlanPanel";
import { MAP_SECTION } from "../map/feedOpen";

export const planPanel: PanelSpec = { ...planPanels[0], optional: true };

/** The Map with the plan review open. */
export function reviewPlan(): void {
  goSection("agents", "map");
  showPanel(MAP_SECTION, planPanel); // kept until the Map lays out (lib/workspace/kept.ts)
}

/** The plan went on (approved) or the run stopped (rejected): the panel leaves the Map. */
export function closePlanReview(): void {
  if (!layoutStore(MAP_SECTION).get().layout?.[planPanel.id]) return;
  hidePanel(MAP_SECTION, planPanel.id);
}
