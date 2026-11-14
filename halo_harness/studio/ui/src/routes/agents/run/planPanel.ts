// The plan review of a goal run on Live (3.0.9.0 R2's plan canvas; 3.4.0.0 D "the runs fold": an optional panel of
// Live's workspace, Runs' console place before). A run started with "Review the plan first" stops after the lead's
// split and waits on you: its lead on Live says so and carries "Review the plan", which opens this panel beside the
// canvas (as does the run's inspector, the palette's "Agents: review the plan" and the supervisor's "open the plan").
// Nothing opens it on its own. While it is open the Live canvas folds to its strip, so the plan has the stage (as it
// had Runs' console's place: nothing runs while the plan waits); Approve and run hands the plan to the waiting run, the
// panel closes and the canvas opens again; Reject does the same.
import type { PanelSpec } from "../../../lib/workspace/types";
import { goSection } from "../../../lib/store";
import { hidePanel, layoutStore, showPanel, whenLaidOut } from "../../../lib/workspace/persist";
import { planPanels } from "../../orchestra/plan/PlanPanel";

export const planPanel: PanelSpec = { ...planPanels[0], optional: true }; // 3.6.0.0 R0a: a tab of the canvas

/** Live with the plan review open beside the canvas. */
export function reviewPlan(): void {
  goSection("agents", "live");
  whenLaidOut("roles", () => showPanel("roles", planPanel)); // a tab: the canvas gives it the main place
}

/** The plan went on (approved) or the run stopped (rejected): the panel leaves Live. */
export function closePlanReview(): void {
  if (!layoutStore("roles").get().layout?.[planPanel.id]) return;
  hidePanel("roles", planPanel.id); // the canvas has the main place again
}
