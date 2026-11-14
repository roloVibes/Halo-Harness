// The palette's Agents lines for this machine's sessions: Agents: Attention (A), Agents: Activity, follow / steer /
// pause / stop the selected agent, follow any live agent by name, pause all, resume all, answer next (the Attention
// panel on the oldest row), record, take over, hand to, replay the selected session, Local: the Ollama steward.
import { goSection } from "../../lib/store";
import { openActivity, openLocalHost } from "../agents/fleetDoor";
import { setAttention, toggleAttention } from "../agents/attention";
import { askStop, everySession, openAgentPanel, select, toggleFollow, togglePause } from "./actions";
import { allAgents, fleet, findAgent, isLive, sessionTitle } from "./store";
import { askHandoff, record } from "./extras";
import { panels } from "./pstore";
import { replaySession } from "../agents/live/replay"; // 3.4.1.0 R1: Live's scrubber
import { focusSteer } from "./Steer";
import { openWorkerRun } from "../agents/run/door";

export type FleetCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

export function fleetCommands(): FleetCommand[] {
  const s = fleet.get();
  const g = "Agents";
  const waiting = panels.get().attention.length;
  const out: FleetCommand[] = [
    { id: "fleet-attention", group: g, label: "Agents: Attention", hint: `${waiting} waiting · every decision, one key each`, kbd: "A", run: () => (goSection("agents"), toggleAttention()) },
    { id: "fleet-activity", group: g, label: "Agents: Activity", hint: "the timeline strip and the merged live log of every session", run: openActivity },
    { id: "fleet-follow", group: g, label: s.follow ? "Agents: stop following the agent" : "Agents: follow the agent", hint: "the stream scrolls with it", kbd: "F", run: toggleFollow },
    { id: "fleet-pause-all", group: g, label: "Agents: pause all", hint: "every session holds at its next tool or model call", run: () => void everySession("pause") },
    { id: "fleet-resume-all", group: g, label: "Agents: resume all", hint: "every paused session carries on", run: () => void everySession("resume") },
    { id: "fleet-answer-next", group: g, label: "Agents: answer next", hint: `${waiting} waiting · Attention, the oldest row`, run: () => (panels.update((p) => ({ attnSel: p.attention[0]?.id || "" })), goSection("agents"), setAttention(true)) },
    { id: "fleet-ollama", group: g, label: "Local: the Ollama steward", hint: "each host's card, models, findings and fit plan", run: () => openLocalHost() },
  ];
  const sel = s.selected ? findAgent(s, s.selected) : null;
  if (sel) {
    const name = sel.a.name || sel.a.agent_id;
    out.push(
      { id: "fleet-steer", group: g, label: `Agents: steer ${name}`, hint: "the Steer box: a nudge or a new task", run: () => (openAgentPanel(sel.key), focusSteer("agent")) },
      { id: "fleet-pause", group: g, label: `Agents: ${sel.a.state === "paused" ? "resume" : "pause"} ${name}`, kbd: "P", run: () => void togglePause(sel.key) },
      { id: "fleet-stop", group: g, label: `Agents: stop ${name}`, hint: "asks first", run: () => askStop(sel.key) },
      { id: "fleet-takeover", group: g, label: `Agents: take over ${name}`, hint: "your brief replaces its task, recorded as a hand-off", run: () => askHandoff("take_over", sel.key) },
      { id: "fleet-handto", group: g, label: `Agents: hand ${name} to...`, hint: "its task as a written brief; it stops", run: () => askHandoff("hand_to", sel.key) },
      { id: "fleet-record", group: g, label: `Agents: record ${name}`, hint: "one HTML file that replays anywhere", run: () => void record(sel.key, true) },
    );
    if (sel.h.local) out.push({ id: "fleet-replay", group: g, label: "Agents: replay this session on Live", hint: "drag the scrubber back, or Play", run: () => void replaySession(sel.s.session_id) });
    if (sel.s.kind === "orchestra-worker") out.push({ id: "fleet-orchestra", group: g, label: "Agents: open this session's run", hint: "its lane on Live, or its report in History", run: () => openWorkerRun(String(sel.s.cwd || "")) });
  }
  for (const r of allAgents(s).filter((x) => isLive(x.a)).slice(0, 24))
    out.push({
      id: "fleet-agent-" + r.key,
      group: g,
      label: `Agents: follow agent ${r.a.name || r.a.agent_id}`,
      hint: `${r.a.state} · ${r.h.name || ""} · ${sessionTitle(r.s)}`,
      run: () => (select(r.key), openAgentPanel(r.key)),
    });
  return out;
}
