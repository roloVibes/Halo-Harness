// What each Session panel is (`about`, one line) and how to use it (`help`,
// a few short lines), 3.1.4.0 R2; routes/help.ts merges them into HELP. The
// Map, Agent, Activity and Attention panels are Fleet's, scoped to this
// harness and the session you chose; Live and Cost are Session's own
// (3.1.5.0 R3: Live fills the right side, Agent, Activity and Attention
// start as strips; 3.1.7.0 R1: Live has Fleet's columns, its timeline strip
// and filters, and the Steer box at its foot at all times).
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const SESSION_HELP: Record<string, Help> = {
  "session-live": {
    about: "Every agent here at once, live: what it types, each tool call and its result, what it hands back, what it asks you.",
    help: lines(
      "Lines land in the order they happen, in Fleet's columns: the time, the kind (TOOL, TEXT, STATE, ASK, YOU...) and the agent's tag (its colour, its name and its state: cyan works, amber waits, green done, red failed).",
      "A tool call is one row: runs Bash, what it runs on, the time ticking while it runs, then the first line of its result; click the row for the whole result.",
      "On top, the timeline: a lane per live agent of this session over 5, 15 or 60 minutes; click a lane to show only that agent. The agent and kind picks beside Follow narrow the lines.",
      "Steer is always at the bottom: it talks to the agent you pinned, else the session's main agent, with Pause and Stop beside it. Hover a tag or a map node and click steer: that agent, the box ready to type.",
      "Click a tag: only that agent; the tag again (or Esc) shows everyone. Follow keeps the newest line in view; scroll up and it pauses, ↓ N new brings you back. Hover a line: its node lights on the map.",
      "An ask lands as an amber card with its A / R / S / O answers; the newest 500 lines stay here, the full log is in Activity.",
    ),
  },
  "session-map": {
    about: "Your sessions on this machine, each one's agents as a tree: who spawned whom, the model, the cost, the tool running now.",
    help: lines(
      "Each agent sits under the one that spawned it; a node shows its model, what it costs and, while a tool runs, its name and time (Bash 12s).",
      "A cyan pulse works, amber waits on you, green just finished (it fades), red failed (it stays); the edge to it glows the same.",
      "Click an agent to select it (its session becomes the chosen one); double-click opens Agent expanded; hover it and click steer to steer it from Live; the ... menu has Steer, Pause, Stop, Take over, Hand to, Record.",
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
      "The spend, the tokens, the turns and the context move the moment the terminal's status bar does: at the end of each model call and at each turn's start and end.",
      "The sparkline beside the spend is the spend since this page opened; the context bar is how full the model's context is: amber past 80 %, red past 95 %.",
      "Turns are your turns in the session, as the terminal counts them; per turn is the spend over them. An agent's own model calls show as calls on its line.",
      "The stacked bar is each agent's own share, its tokens in and out beside it: a finished sub-agent counts once, on its own line (main's share is the total less its finished sub-agents'); a running sub-agent's spend joins the total when it finishes.",
      "Choose another session on the map (or in Activity's session pick) and Cost follows it.",
    ),
  },
};
