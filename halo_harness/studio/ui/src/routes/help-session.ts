// What each Session panel is (`about`, one line) and how to use it (`help`,
// a few short lines), 3.1.4.0 R2; routes/help.ts merges them into HELP. The
// Map, Agent, Activity and Attention panels are Fleet's, scoped to this
// harness and the session you chose; Live and Cost are Session's own
// (3.1.5.0 R3: Live fills the right side, Agent, Activity and Attention
// start as strips; 3.1.7.0 R1: Live has Fleet's columns, its timeline strip
// and filters, and the Steer box at its foot; 3.6.0.11: off until asked for).
import type { Help } from "./help-orchestra";
import { NAV_HELP } from "../lib/canvasNav"; // 3.4.1.3: zoom and pan, the same on every drawing
import { WAS, WORDS } from "./crew/map/truthWords";

// 3.6.0.2 R35: the two panels swapped names this release: the drawer that draws the run is Live (it was Map), the
// line-by-line panel is Feed (it was Live). The "(was ...)" hovers go next release.

const lines = (...l: string[]) => l.join("\n");

export const SESSION_HELP: Record<string, Help> = {
  "session-live": {
    about: `Every agent here at once, line by line: what it types, each tool call and its result, what it hands back, what it asks you. ${WAS.feed}`,
    help: lines(
      "The header's last line names the session the lines are of (its folder, title, start and terminal), with Change session; N other sessions running opens the same list. Session follows the newest session you start unless you picked one yourself (Change session, the Map, a link), never while the Prompt box holds text, and says Now typing into ... when it moves.",
      "Lines land in the order they happen, in Fleet's columns: the time, the kind (TOOL, TEXT, THINK, TALK, STATE, ASK, YOU...) and the agent's tag (its colour, its name and its state: cyan works, amber waits, green done, red failed).",
      "THINK is a model's reasoning as it comes, one row per thought: four lines, show all for the rest, then how long it thought (and its tokens when the provider says). Its chip says what it led to; why? on that row opens the thought under it. Thinking beside Follow shows only the thoughts and what each led to. A model with no thinking shows none.",
      "TALK is one agent's words to another: the speaker's tag, an arrow, the listener's, and why (TASK, HAND-BACK, STEER, SQUARE, HAND-OVER). A hand-back is one row (the same words as the agent's last ones). Conversations (its button in the bar) shows them as threads.",
      "A tool call is one row: runs Bash, what it runs on, the time ticking while it runs, then the first line of its result; click the row for the whole result.",
      "On top, the timeline: a lane per live agent of this session over 5, 15 or 60 minutes, drawn by what it does: thinking (violet), running a tool (cyan), writing (green), waiting on you (amber), idle (a thin line). Hover a segment for its length; click a thinking one to scroll to that thought; click a lane to show only that agent. The agent and kind picks beside Follow narrow the lines.",
      "Steer (the header button, a row's steer, or s on a row) opens the steer box at the bottom; x or Esc closes it; its line says who it reaches and what that agent does now (Steering: coder · Bash (pytest -q), 12 s). Click a row or a map node to make it the target (it stays outlined), Tab / Shift+Tab in the field cycle the live agents, s on a focused row steers it. Your steer lands under its target; the agent's next row says after your steer.",
      "Click a tag: only that agent; the tag again (or Esc) shows everyone. Follow keeps the newest line in view; while you type a steer or have scrolled up the view holds still and N new rows · follow (or Esc out of the field) brings you back. Export saves the session export: the session as one Markdown file.",
      "An ask lands as an amber card with its A / R / S / O answers; the newest 500 lines stay here, the full log is in Activity.",
      "The small word on the bar is the session's permission mode (auto, default, acceptEdits, plan...); hover it for what the mode lets run. Shift+Tab in the terminal or /plan changes it, and the word follows.",
    ),
  },
  "session-prompt": { // 3.3.11.0 R1
    about: "Type into the chosen session as in the terminal, and see what became of what you typed.",
    help: lines(
      "Enter sends, Shift+Enter is a new line; Up goes to the start of the prompt, Down to its end, and from there Up / Down walk this session's history, as in the terminal; Alt+Enter (or the palette) opens this panel with the keyboard in it.",
      "The box is three lines at the least, grows with what you type and takes the panel's free room while the conversation is short; past twelve lines it scrolls.",
      "/ opens the slash list, the terminal's own commands and the session's custom ones, filtered as you type: Tab completes, Esc closes; a / line runs in the session and its output lands here.",
      "A line that starts with ! runs that command in the session at once, as in the terminal: no model turn; its output shows here and in the Feed.",
      "While a turn runs, a send asks first: Queue it starts it when that turn ends (one at a time), Steer puts it into the running turn. A pasted image or a dropped file rides along.",
      "Beside each of your turns, four marks: sent (Studio stored it), delivered (the session took it), read (it is in the model's input), replied (that turn ended); red when it failed, the reason in its title.",
      "The conversation reads like the terminal: replies, one line per tool call, the asks with their buttons. The ${WORDS.feed} stays the stream for steering.",
    ),
  },
  "session-conversations": { // 3.3.16.2
    about: "Agents talking to each other: each pair's messages as one thread, the task, the hand-back, a steer, a square, a hand-over.",
    help: lines(
      "Left: every pair of agents that has talked, the newest first, with how many messages and the last line.",
      "Right: the chosen pair's thread. Each message sits on its speaker's side, with why it was said (TASK, HAND-BACK, STEER, SQUARE, HAND-OVER) and when; a reply sits under what it answers.",
      `Click a message to see it in the ${WORDS.feed}; show in the ${WORDS.feed} narrows the ${WORDS.feed} to this pair (the chip in the ${WORDS.feed}'s header shows everything again).`,
      `Its button in the bar counts the threads and the messages. The ${WORDS.feed}'s TALK rows are the same messages, as they happen.`,
    ),
  },
  "session-map": {
    about: `What the chosen session is doing now, drawn top to bottom on the map it runs on. ${WAS.live}`,
    help: lines(
      "On top, one true block: which map this session runs on and since when; when new sessions run on another map, the sentence that says so and a New session button. Under it, one status line: who works on what, what it waits for, the cost.",
      "Below, the session drawn: main on the first row, then its boxes two a row; a lit box works now. Nothing is cut: \"↓ n more below\" scrolls one row.",
      "A cyan pulse works, amber waits on you, green just finished, red failed. While the pointer is on the drawing it holds still.",
      `Open it on the ${WORDS.map} tab (Agents -> 3 · ${WORDS.map}) for the plan itself; a goal run's pages and its report open in that tab's drawer.`,
      `${NAV_HELP} It opens at 100 %, never smaller than its text reads; Fit (or 0) goes back to the top.`,
    ),
  },
  "session-agent": {
    about: "The selected agent: what it thinks, what it runs, what it hands back; steer it.",
    help: lines(
      `A drawer beside the ${WORDS.feed}: its button in the bar opens it (double-click an agent on the map opens it too).`,
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
      `Cards (permission, question, plan, approval), gates, paused agents and spend caps of this harness; each also lands in the ${WORDS.feed} as it arrives.`,
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
