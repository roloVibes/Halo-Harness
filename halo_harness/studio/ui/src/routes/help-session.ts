// What each Session panel is (`about`, one line) and how to use it (`help`,
// a few short lines), 3.1.4.0 R2; routes/help.ts merges them into HELP. The
// panels are Fleet's, scoped to this harness and the session you chose.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const SESSION_HELP: Record<string, Help> = {
  "session-map": {
    about: "Your sessions on this machine as cards, each one's agents as a tree; the one at work lit.",
    help: lines(
      "A flowing outline is an agent at work, amber waits on you, green just finished, red failed.",
      "Click an agent to see it in Agent (the session it is in becomes the chosen one); double-click opens Agent expanded.",
      "The ... on a card or an agent: Steer, Pause, Stop, Take over, Hand to, Record, Shutdown.",
      "J / K hop between this harness's live agents; Fleet (Alt+4) still shows every harness.",
    ),
  },
  "session-agent": {
    about: "The selected agent: what it thinks, what it runs, what it hands back; steer it.",
    help: lines(
      "Thinking is its text as it types it, Working one row per tool call, Output its hand-back.",
      "Steer: a nudge it reads before its next step, or redirect to give it a new task.",
      "Pause holds it at its next step; Stop asks first (K here does the same).",
      "F follows, Space pins a mini stream that stays on screen in every section.",
    ),
  },
  "session-activity": {
    about: "What the chosen session does: a timeline lane per live agent over its live log.",
    help: lines(
      "Each lane shows an agent's states over 5, 15 or 60 minutes; the ticks are its tool calls.",
      "The session pick switches between the chosen session and every session on this harness.",
      "Filter by agent or kind; Follow keeps the newest line in view; click a line to select that agent.",
    ),
  },
  "session-attention": {
    about: "What waits on you in this harness's sessions, oldest first, one key each.",
    help: lines(
      "Cards (permission, question, plan, approval), gates, paused agents and spend caps of this harness.",
      "A accepts or allows, R denies or redoes with your text, S stops, O opens the panel it belongs to.",
      "J / K (or the arrows) move between rows while this panel has the focus.",
    ),
  },
  "session-cost": {
    about: "What the chosen session has cost so far: spend, tokens in and out, turns, elapsed, model.",
    help: lines(
      "The spend ticks up as the session's model answers; each agent's own cost is listed under it.",
      "Tokens and turns are the session's own figures, read from its control socket with the map.",
      "Choose another session on the map (or in Activity's session pick) and Cost follows it.",
    ),
  },
};
