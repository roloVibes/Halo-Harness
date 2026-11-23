// What an agent does now, in one line (3.6.0.17 N1: moved here from nodeBits.ts, which re-exports it, so node can load
// it without React): the Agent panel's glance and the pinned agent's panel read it. A running tool is named by the ONE
// rule a box's NOW uses (truthToolWords.ts toolWords): "Bash ls -la", an MCP tool without its raw JSON arguments.
import type { AgentRow } from "../../fleet/types";
import { toolWords } from "../map/truthToolWords";

/** One line: what the agent does now (waits on you, paused, queued, its tool, how it ended, else its task). */
export function nowText(a: AgentRow): string {
  if (a.state === "waiting") return "waits on you";
  if (a.state === "paused") return "paused: holds at its next step";
  if (a.state === "queued") return "queued";
  if (a.current) return toolWords(a.current);
  if (a.state === "done" || a.state === "failed" || a.state === "stopped") return `${a.state}${a.last_text ? ": " + a.last_text : ""}`;
  return a.task || "";
}
