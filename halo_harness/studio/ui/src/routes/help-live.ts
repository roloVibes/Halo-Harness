// What the two live panels are (`about`, one line) and how to use them (`help`, a few short lines); routes/help.ts
// merges them into HELP. It keeps its panel id: Attention (Agents' chip, every view). Activity's entry went: no panel reads
// it (P4 batch 12).
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const LIVE_HELP: Record<string, Help> = {
  "fleet-attention": {
    about: "Every decision that waits on you, oldest first, one key each.",
    help: lines(
      "Cards (permission, question, plan, approval), gates, paused agents, spend caps and file conflicts all land here.",
      "A accepts or allows, R denies or redoes with your text, S stops, O opens where it belongs (Agents, Local).",
      "J / K (or the arrows) move between rows while this panel has the focus.",
      "The chip on Agents' bar counts them in every view, amber while any waits; it (or A) opens and closes this panel.",
    ),
  },
};
