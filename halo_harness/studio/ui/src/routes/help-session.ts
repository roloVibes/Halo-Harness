// What each Session panel is (`about`, one line) and how to use it (`help`,
// a few short lines), 3.1.4.0 R2; routes/help.ts merges them into HELP. The
// Map, Agent, Activity and Attention panels are Fleet's, scoped to this
// harness and the session you chose; Live and Cost are Session's own
// (3.1.5.0 R3: Live fills the right side, Agent, Activity and Attention
// start as strips; 3.1.7.0 R1: Live has Fleet's columns, its timeline strip
// and filters, and the Steer box at its foot at all times).
import type { Help } from "./help-orchestra";
import { NAV_HELP } from "../lib/canvasNav"; // 3.4.1.3: zoom and pan, the same on every drawing

const lines = (...l: string[]) => l.join("\n");

export const SESSION_HELP: Record<string, Help> = {
  "session-live": {
    about: "Every agent here at once, live: what it types, each tool call and its result, what it hands back, what it asks you.",
    help: lines(
      "Lines land in the order they happen, in Fleet's columns: the time, the kind (TOOL, TEXT, THINK, TALK, STATE, ASK, YOU...) and the agent's tag (its colour, its name and its state: cyan works, amber waits, green done, red failed).",
      "THINK is a model's reasoning as it comes, one row per thought: four lines, show all for the rest, then how long it thought (and its tokens when the provider says). Its chip says what it led to; why? on that row opens the thought under it. Thinking beside Follow shows only the thoughts and what each led to. A model with no thinking shows none.",
      "TALK is one agent's words to another: the speaker's tag, an arrow, the listener's, and why (TASK, HAND-BACK, STEER, SQUARE, HAND-OVER). A hand-back is one row (the same words as the agent's last ones). Conversations (its button in the bar) shows them as threads.",
      "A tool call is one row: runs Bash, what it runs on, the time ticking while it runs, then the first line of its result; click the row for the whole result.",
      "On top, the timeline: a lane per live agent of this session over 5, 15 or 60 minutes, drawn by what it does: thinking (violet), running a tool (cyan), writing (green), waiting on you (amber), idle (a thin line). Hover a segment for its length; click a thinking one to scroll to that thought; click a lane to show only that agent. The agent and kind picks beside Follow narrow the lines.",
      "Steer is always at the bottom; its line says who it reaches and what that agent does now (Steering: coder · Bash (pytest -q), 12 s). Click a row or a map node to make it the target (it stays outlined), Tab / Shift+Tab in the field cycle the live agents, s on a focused row steers it. Your steer lands under its target; the agent's next row says after your steer.",
      "Click a tag: only that agent; the tag again (or Esc) shows everyone. Follow keeps the newest line in view; while you type a steer or have scrolled up the view holds still and N new rows · follow (or Esc out of the field) brings you back. Export saves the session as one Markdown trace.",
      "An ask lands as an amber card with its A / R / S / O answers; the newest 500 lines stay here, the full log is in Activity.",
      "The small word on the bar is the session's permission mode (auto, default, acceptEdits, plan...); hover it for what the mode lets run. Shift+Tab in the terminal or /plan changes it, and the word follows.",
    ),
  },
  "session-prompt": { // 3.3.11.0 R1
    about: "Type into the chosen session as in the terminal, and see what became of what you typed.",
    help: lines(
      "Enter sends, Shift+Enter is a new line, Up / Down walk this session's history; Alt+Enter (or the palette) opens this panel with the keyboard in it.",
      "The box is three lines at the least, grows with what you type and takes the panel's free room while the conversation is short; past twelve lines it scrolls.",
      "/ opens the slash list, the terminal's own commands and the session's custom ones, filtered as you type: Tab completes, Esc closes; a / line runs in the session and its output lands here.",
      "While a turn runs, a send asks first: Queue it starts it when that turn ends (one at a time), Steer puts it into the running turn. A pasted image or a dropped file rides along.",
      "Beside each of your turns, four marks: sent (Studio stored it), delivered (the session took it), read (it is in the model's input), replied (that turn ended); red when it failed, the reason in its title.",
      "The conversation reads like the terminal: replies, one line per tool call, the asks with their buttons. Live stays the stream for steering.",
    ),
  },
  "session-conversations": { // 3.3.16.2
    about: "Agents talking to each other: each pair's messages as one thread, the task, the hand-back, a steer, a square, a hand-over.",
    help: lines(
      "Left: every pair of agents that has talked, the newest first, with how many messages and the last line.",
      "Right: the chosen pair's thread. Each message sits on its speaker's side, with why it was said (TASK, HAND-BACK, STEER, SQUARE, HAND-OVER) and when; a reply sits under what it answers.",
      "Click a message to see it in Live; show in Live narrows Live to this pair (the chip in Live's header shows everything again).",
      "Its button in the bar counts the threads and the messages. Live's TALK rows are the same messages, as they happen.",
    ),
  },
  "session-map": {
    about: "Your sessions on this machine, each one's agents as a tree: who spawned whom, the model, the cost, the tool running now.",
    help: lines(
      "Each agent sits under the one that spawned it; a node shows its model, what it costs and, while a tool runs, its name and time (Bash 12s).",
      "A cyan pulse works, amber waits on you, green just finished (it fades), red failed (it stays); the edge to it glows the same.",
      "Click an agent to select it (its session becomes the chosen one); double-click opens Agent expanded; hover it and click steer to steer it from Live; the ... menu has Steer, Pause, Stop, Take over, Hand to, Record.",
      "J / K hop between this harness's live agents; Agents (Alt+2) on Live shows every harness (its fleet scope).",
      `${NAV_HELP} The Map opens fitted to the panel, never smaller than its text reads: a bigger tree opens on the main agent, and Fit (or 0) shows it all.`,
    ),
  },
  "session-agent": {
    about: "The selected agent: what it thinks, what it runs, what it hands back; steer it.",
    help: lines(
      "A drawer beside Live: its button in the bar opens it (double-click an agent on the map opens it too).",
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
