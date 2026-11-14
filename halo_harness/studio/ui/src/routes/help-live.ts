// What the two live panels are (`about`, one line) and how to use them (`help`, a few short lines); routes/help.ts
// merges them into HELP. They keep their panel ids: Attention (Agents' chip, every view) and Activity (Agents -> Live,
// optional).
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const LIVE_HELP: Record<string, Help> = {
  "fleet-attention": {
    about: "Every decision that waits on you, oldest first, one key each.",
    help: lines(
      "Cards (permission, question, plan, approval), gates, paused agents, spend caps and file conflicts all land here.",
      "A accepts or allows, R denies or redoes with your text, S stops, O opens where it belongs (Live, Local).",
      "J / K (or the arrows) move between rows while this panel has the focus.",
      "The chip on Agents' bar counts them in every view, amber while any waits; it (or A) opens and closes this panel.",
    ),
  },
  "fleet-activity": {
    about: "What your sessions do: a timeline lane per live agent and the merged live log.",
    help: lines(
      "Add it on Live with the + in the header (or the palette's Agents: Activity); it floats over the tree.",
      "Each lane shows the agent's states over 5, 15 or 60 minutes; the ticks are its tool calls.",
      "Hover a bar for who and when; click a lane or a line to select that agent on the tree.",
      "Filter the log by session, agent or kind; Follow keeps the newest line in view.",
    ),
  },
};
