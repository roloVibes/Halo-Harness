// "make it" (3.6.0.0 R2; the design: "make it opens the agent creator pre-filled, then comes back"): a proposal card in
// the builder's preview, or "+ Add a step" -> a new agent. The agent form (1 · Agents) opens filled in, not saved; the
// proposal's own lines leave the preview (the form makes the agent now, not Apply). Save there brings you back to
// 2 · Workflows on the same workflow -- with the new agent in a new step when it came from "+ Add a step".
import { toast } from "../../../lib/store";
import { setAgentsView } from "../../agents/store";
import { untickTarget } from "../builderStore";
import { fillAgent, onSavedFor } from "../store";
import { blank, type Change } from "../types";
import { addStep, flows, refreshCost } from "./flowStore";

let stepFor = ""; // the workflow whose "+ Add a step" made the agent: the step is added when it is saved

export function makeIt(c: Change): void {
  if (!c.body) return;
  untickTarget(c.target);
  stepFor = "";
  fillAgent(c.body, flows.get().form?.name || "the workflow");
  setAgentsView("crew");
}

export function makeForStep(): void {
  const name = flows.get().form?.name || "the workflow";
  stepFor = name;
  flows.update(() => ({ adding: false }));
  fillAgent({ ...blank("new-agent"), does: "" }, name);
  setAgentsView("crew");
}

onSavedFor((agent, workflow) => {
  setAgentsView("flows");
  if (stepFor && flows.get().form?.name === stepFor) addStep(agent);
  else refreshCost();
  stepFor = "";
  toast(`Saved ${agent}; back to ${workflow}.`, "done");
});
