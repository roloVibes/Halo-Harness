// What each fleet panel is (`about`, one line) and how to use it (`help`, a few short lines); routes/help.ts merges them
// into HELP. 3.3.16.0 R2 "the Fleet fold": the Fleet section went and three of its panels moved, keeping their ids --
// Attention (Agents' chip, every view), Activity (Agents -> Live, optional) and Mission (Agents -> Live, optional). What
// People, Costs, Health, Capabilities, the Map, the Tree and the Agent panel said is Live's inspector now (a machine's
// summary, the agent inspector) and Setup -> Machines; the Ollama panel's lines are Local -> Hosts'.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const FLEET_HELP: Record<string, Help> = {
  "fleet-attention": {
    about: "Every decision that waits on you, across the fleet, oldest first, one key each.",
    help: lines(
      "Cards (permission, question, plan, approval), gates, paused agents, spend caps, file conflicts and missions (a plan to approve, a refused edit, a hub asking to run a part here) all land here.",
      "A accepts or allows, R denies or redoes with your text, S stops, O opens where it belongs (Live, Runs, Local).",
      "J / K (or the arrows) move between rows while this panel has the focus.",
      "The chip on Agents' bar counts them in every view, amber while any waits; it (or A) opens and closes this panel.",
    ),
  },
  "fleet-activity": {
    about: "What the whole fleet does: a timeline lane per live agent and the merged live log.",
    help: lines(
      "Add it on Live with the + in the header (or the palette's Agents: Activity); it floats over the tree.",
      "Each lane shows the agent's states over 5, 15 or 60 minutes; the ticks are its tool calls.",
      "Hover a bar for who and when; click a lane or a line to select that agent on the tree.",
      "Filter the log by harness, session, agent or kind; Follow keeps the newest line in view.",
    ),
  },
  "fleet-mission": {
    about: "One goal for the whole fleet: the hub's lead splits it into parts by what each machine can do; you approve, it runs, the report says who did what.",
    help: lines(
      "Type the goal, constraints, the machines to prefer (click in order) and a budget; Plan it asks the hub's lead for the parts.",
      "The plan draws on Agents -> Live (fleet): a node per part under its machine, a lock where only that machine has what it needs, amber where two parts wait on each other's files.",
      "Drag a part's node into another machine's box to move it (it snaps back with the reason when that machine lacks a need); Drop takes it out; Plan again asks anew.",
      "Approve, then Run (Run approves first): asked parts wait on that member's owner, running ones show their agent's line and what each owns; Stop asks for a reason.",
      "The report: who did what on which machine, cost per machine and per part, decisions, refused edits, the merge, the artifacts to open.",
    ),
  },
};
