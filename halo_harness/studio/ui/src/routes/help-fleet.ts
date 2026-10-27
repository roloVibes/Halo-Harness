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
      "Cards (permission, question, plan, approval), gates, paused agents, spend caps, file conflicts and missions (a plan to approve, a refused edit, a hub asking to run a part here) all land here.",
      "A accepts or allows, R denies or redoes with your text, S stops, O opens the panel it belongs to.",
      "J / K (or the arrows) move between rows while this panel has the focus.",
      "The count shows in the status bar in every section, and at the top of the Tree panel.",
    ),
  },
  "fleet-tree": {
    about: "The fleet as a tree: harness, session, agent, each with its status; answer a waiting session here.",
    help: lines(
      "Add it with the + in the header. Click a node: one of this harness opens in Session, a member's is selected on the map.",
      "A session that waits on you has an answer link: type the answer or pick an option without leaving Fleet.",
      "A mission part carries a mission chip; its part link opens the Mission panel on that part.",
      "After ten minutes away the While you were away card shows at the top (the Fleet icon carries a dot meanwhile).",
    ),
  },
  "fleet-map": {
    about: "Every harness as a box, its sessions as cards, each session's agents as a tree.",
    help: lines(
      "A flowing outline is an agent at work, amber waits on you, green just finished, red failed.",
      "Click an agent to see it in Agent; double-click opens Agent expanded.",
      "The ... on a card or an agent: Steer, Pause, Stop, Take over, Hand to, Record, Shutdown, Open in Orchestra.",
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
  "fleet-mission": {
    about: "One goal for the whole fleet: the hub's lead splits it into parts by what each harness can do; you approve, it runs, the report says who did what.",
    help: lines(
      "Type the goal, constraints, the harnesses to prefer (click in order) and a budget; Plan it asks the hub's lead for the parts.",
      "The plan draws on the map: a node per part in its harness box, a lock where only that harness has what it needs, amber where two parts wait on each other's files.",
      "Drag a part's node to another harness to move it (it snaps back with the reason when that harness lacks a need); Drop takes it out; Plan again asks anew.",
      "Approve, then Run (Run approves first): asked parts wait on that member's owner, running ones show their agent's line; Stop asks for a reason.",
      "The report: who did what on which harness, cost per harness and per part, decisions, refused edits, the merge, the artifacts to open.",
    ),
  },
  "fleet-capabilities": {
    about: "What every harness can do: hardware, models, craft apps, MCP servers and tools, skills, tags; and who can do what.",
    help: lines(
      "Expand for one spec card per harness; open an MCP server to see its tools.",
      "Who can... (on the compact face too) ranks the fleet for what you type: an exact name first, then a word of a name, then a word of a description; a tag counts double.",
      "Click a result to pick that harness: its card opens and its box lights on the map.",
      "Recall (expanded, under Who can...) searches what this harness remembers: memory, sessions, the coach library, findings, decisions and your notes; a finding or decision shows its id, who wrote it and when; Fleet asks every harness.",
      "Each harness gathers its own catalog in code and sends a new one when it changes; Refresh asks again now.",
      "Your own words go in fleet.tags; fleet.capabilities.hide keeps a server, tool or skill off the list.",
    ),
  },
};
