// What each Fleet panel is (`about`, one line) and how to use it (`help`, a
// few short lines); routes/help.ts merges them into HELP.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const FLEET_HELP: Record<string, Help> = {
  "fleet-people": {
    about: "Who is in the fleet: each harness, what it shares, what it is on, live or away.",
    help: lines(
      "One row per harness: host, Halo version, share and control levels, project and top session, spend today.",
      "live = an agent of it works now, idle = it answers but nothing runs, away = the hub has not heard from it for two minutes.",
      "A version chip means another Halo version: run halo update on the older one.",
      "Message sends its owner a note in that session (the model never reads it); Kick asks first.",
    ),
  },
  "fleet-costs": {
    about: "What the fleet spends today: the whole fleet, each harness, project and session; the caps.",
    help: lines(
      "Today counts the sessions started today, local time.",
      "Set a cap per harness, per project or for the whole fleet; empty means no cap.",
      "A cap reached pauses the sessions in its scope and shows in Attention; Lift for today resumes them.",
      "Provider balances show when the balances workers have read them.",
    ),
  },
  "fleet-health": {
    about: "A doctor summary per harness: providers, versions, disk and control sockets.",
    help: lines(
      "Each harness is read at most once a minute; the age of the reading is on every row.",
      "A member answers over the hub with a read-only doctor check.",
      "Refresh asks every harness again now.",
    ),
  },
  "fleet-attention": {
    about: "Every decision that waits on you, across the fleet, oldest first, one key each.",
    help: lines(
      "Cards (permission, question, plan, approval), gates, paused agents, spend caps and file conflicts all land here.",
      "A accepts or allows, R denies or redoes with your text, S stops, O opens the panel it belongs to.",
      "J / K (or the arrows) move between rows while this panel has the focus.",
      "The count shows in the status bar and the rail in every section.",
    ),
  },
  "fleet-map": {
    about: "Every harness as a box, its sessions as cards, each session's agents as a tree.",
    help: lines(
      "A flowing outline is an agent at work, amber waits on you, green just finished, red failed.",
      "Click an agent to see it in Agent; double-click opens Agent expanded.",
      "The ... on a card or an agent: Steer, Pause, Stop, Take over, Hand to, Record, Shutdown, Open in Orchestra or Flow.",
      "By project puts everyone on one repo in one box, with dirty / ahead / behind and the worktree on each card.",
      "An amber dashed edge joins two agents editing the same file; J / K hop between the live agents.",
    ),
  },
  "fleet-activity": {
    about: "What the whole fleet does: a timeline lane per live agent and the merged live log.",
    help: lines(
      "Each lane shows the agent's states over 5, 15 or 60 minutes; the ticks are its tool calls.",
      "Hover a bar for who and when; click a lane to select that agent on the map.",
      "Filter the log by harness, session, agent or kind; Follow keeps the newest line in view.",
    ),
  },
  "fleet-agent": {
    about: "The selected agent: what it thinks, what it runs, what it hands back; steer it.",
    help: lines(
      "Thinking is its text as it types it, Working one row per tool call, Output its hand-back.",
      "Steer: a nudge it reads before its next step, or redirect to give it a new task.",
      "Pause holds it at its next step; Stop asks first (K here does the same).",
      "Take over gives it your brief; Hand to... passes it to another harness; Record saves it as one HTML file; Replay plays its session on the Roles canvas.",
      "F follows, Space pins a mini stream; with no agent picked, the last sessions here can be replayed.",
    ),
  },
  "fleet-capabilities": {
    about: "What every harness can do: hardware, models, craft apps, MCP servers and tools, skills, tags; and who can do what.",
    help: lines(
      "Expand for one spec card per harness; open an MCP server to see its tools.",
      "Who can... (on the compact face too) ranks the fleet for what you type: an exact name first, then a word of a name, then a word of a description; a tag counts double.",
      "Click a result to pick that harness: its card opens and its box lights on the map.",
      "Each harness gathers its own catalog in code and sends a new one when it changes; Refresh asks again now.",
      "Your own words go in fleet.tags; fleet.capabilities.hide keeps a server, tool or skill off the list.",
    ),
  },
};
