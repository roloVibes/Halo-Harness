// What each Fleet panel is (`about`, one line) and how to use it (`help`, a
// few short lines); routes/help.ts merges them into HELP.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const FLEET_HELP: Record<string, Help> = {
  "fleet-map": {
    about: "Every harness as a box, its sessions as cards, each session's agents as a tree.",
    help: lines(
      "A flowing outline is an agent at work, amber waits on you, green just finished, red failed.",
      "Click an agent to see it in Agent; double-click opens Agent expanded.",
      "The ... on a card or an agent: Steer, Pause, Stop, Shutdown, Open in Orchestra or Flow.",
      "By project puts everyone on the same repo in one box, the harness colour on each card.",
      "J / K hop between the live agents; an edge lights when an agent spawns or messages another.",
    ),
  },
  "fleet-agent": {
    about: "The selected agent: what it thinks, what it runs, what it hands back; steer it.",
    help: lines(
      "Thinking is its text as it types it, Working one row per tool call, Output its hand-back.",
      "Steer: a nudge it reads before its next step, or redirect to give it a new task.",
      "Pause holds it at its next step; Stop asks first (K here does the same).",
      "F follows (the stream scrolls with it); Space pins it as a mini stream over any section.",
      "Settings (the ... menu) shows the three streams side by side.",
    ),
  },
};
