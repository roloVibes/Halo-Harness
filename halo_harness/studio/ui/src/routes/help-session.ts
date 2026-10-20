// What each Session panel is (`about`, one line) and how to use it (`help`,
// a few short lines), 3.1.4.0 R2; routes/help.ts merges them into HELP. The
// Map, Agent, Activity and Attention panels are Fleet's, scoped to this
// harness and the session you chose; Live and Cost are Session's own
// (3.1.5.0 R3: Live fills the right side, Agent, Activity and Attention
// start as strips).
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const SESSION_HELP: Record<string, Help> = {
  "session-live": {
    about: "Every agent here at once, live: what it types, each tool call and its result, what it hands back, what it asks you.",
    help: lines(
      "Lines land in the order they happen; each one is tagged with its agent: its colour, its name and its state (cyan works, amber waits, green done, red failed).",
      "A tool call is one row: the tool, what it runs on, the time ticking while it runs, then the first line of its result.",
      "Follow keeps the newest line in view; scroll up and it pauses, ↓ N new brings you back.",
      "Click a tag: only that agent, with Steer at the bottom; the tag again (or Esc) shows everyone. Hover a line: its node lights on the map.",
      "An ask lands as an amber card with its A / R / S / O answers; the newest 500 lines stay here, the full log is in Activity.",
    ),
  },
  "session-map": {
    about: "Your sessions on this machine, each one's agents as a tree: who spawned whom, the model, the cost, the tool running now.",
    help: lines(
      "Each agent sits under the one that spawned it; a node shows its model, what it costs and, while a tool runs, its name and time (Bash 12s).",
      "A cyan pulse works, amber waits on you, green just finished (it fades), red failed (it stays); the edge to it glows the same.",
      "Click an agent to select it (its session becomes the chosen one); double-click opens Agent expanded; the ... menu has Steer, Pause, Stop, Take over, Hand to, Record.",
      "J / K hop between this harness's live agents; Fleet (Alt+4) still shows every harness.",
    ),
  },
  "session-agent": {
    about: "The selected agent: what it thinks, what it runs, what it hands back; steer it.",
    help: lines(
      "A strip until you open it (double-click an agent on the map opens it too).",
      "Thinking is its text as it types it, Working one row per tool call, Output its hand-back.",
      "Steer: a nudge it reads before its next step, or redirect to give it a new task. Pause holds it at its next step; Stop asks first (K here does the same).",
      "F follows, Space pins a mini stream that stays on screen in every section.",
    ),
  },
  "session-activity": {
    about: "What the chosen session does: a timeline lane per live agent over its full live log.",
    help: lines(
      "Each lane shows an agent's states over 5, 15 or 60 minutes; the ticks are its tool calls.",
      "The session pick switches between the chosen session and every session on this harness.",
      "Filter by agent or kind; Follow keeps the newest line in view; click a line to select that agent.",
    ),
  },
  "session-attention": {
    about: "What waits on you in this harness's sessions, oldest first, one key each.",
    help: lines(
      "Cards (permission, question, plan, approval), gates, paused agents and spend caps of this harness; each also lands in Live as it arrives.",
      "A accepts or allows, R denies or redoes with your text, S stops, O opens the panel it belongs to.",
      "J / K (or the arrows) move between rows while this panel has the focus.",
    ),
  },
  "session-cost": {
    about: "What the chosen session has cost: the spend and how it rose, the context filling, cost per turn, each agent's share.",
    help: lines(
      "The spend ticks up as the session's model answers; the sparkline beside it is the spend since this page opened.",
      "The context bar is how full the model's context is: amber past 80 %, red past 95 %.",
      "Per turn is the spend over the turns; the stacked bar is each agent's share, its tokens in and out beside it.",
      "Choose another session on the map (or in Activity's session pick) and Cost follows it.",
    ),
  },
};
