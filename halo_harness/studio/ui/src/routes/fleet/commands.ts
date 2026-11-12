// The palette's fleet lines (3.3.16.0 R2 "the Fleet fold": the Fleet group became Agents' -- the section went, its
// panels are Agents' Live and Runs, Setup's Machines and Local's Hosts): Agents: Attention (A), Agents: the fleet on
// Live, Agents: Activity, follow / steer / pause / stop the selected agent, follow any live agent by name, pause all,
// resume all, answer next (the Attention panel on the oldest row), record, take over, hand to, replay the selected
// session, while you were away, who can... and the specs of each machine (a machine's summary), the missions'
// (mcommands.ts), Setup: pair a machine, Local: the Ollama steward, and kick a member.
import { goSection } from "../../lib/store";
import { openActivity, openFleetLive, openLocalHost } from "../agents/fleetDoor";
import { setAttention, toggleAttention } from "../agents/attention";
import { setMachinePage } from "../agents/live/scope";
import { goto as gotoSetup } from "../setup/pages";
import { askStop, everySession, kick, openAgentPanel, select, toggleFollow, togglePause } from "./actions";
import { allAgents, fleet, findAgent, isLive, sessionTitle } from "./store";
import { checkAway } from "./Digest";
import { askHandoff, record } from "./extras";
import { panels } from "./pstore";
import { replaySession } from "../agents/live/replay"; // 3.4.1.0 R1: Live's scrubber
import { startFleet } from "./sync";
import { caps } from "./caps";
import { missionCommands } from "./mcommands";
import { focusSteer } from "./Steer";
import { openWorkerRun } from "../agents/run/door";

export type FleetCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

/** Agents -> Live on the fleet, then `fn` (the tree and the stores are up). */
function onLive(fn: () => void): () => void {
  return () => {
    startFleet();
    openFleetLive();
    window.setTimeout(fn, 80);
  };
}

const local = () => fleet.get().harnesses.find((h) => h.local)?.id || "";

export function fleetCommands(): FleetCommand[] {
  const s = fleet.get();
  if (!s.pack) return []; // 3.4.0.0 C: the fleet is a pack; off, the palette has no fleet line
  const g = "Agents";
  const waiting = panels.get().attention.length;
  const out: FleetCommand[] = [
    { id: "fleet-attention", group: g, label: "Agents: Attention", hint: `${waiting} waiting · every decision across the fleet, one key each`, kbd: "A", run: () => (goSection("agents"), toggleAttention()) },
    { id: "fleet-live", group: g, label: "Agents: the fleet on Live", hint: "every machine, its sessions and their agents (F on the canvas)", run: () => openFleetLive() },
    { id: "fleet-activity", group: g, label: "Agents: Activity", hint: "the timeline strip and the merged live log of every machine", run: openActivity },
    { id: "fleet-pair", group: g, label: "Setup: pair a machine", hint: "a one-time six-word code and its QR for another machine", run: () => (gotoSetup("machines"), goSection("setup")) },
    { id: "fleet-follow", group: g, label: s.follow ? "Agents: stop following the agent" : "Agents: follow the agent", hint: "the stream scrolls with it", kbd: "F", run: toggleFollow },
    { id: "fleet-pause-all", group: g, label: "Agents: pause all", hint: "every session holds at its next tool or model call", run: () => void everySession("pause") },
    { id: "fleet-resume-all", group: g, label: "Agents: resume all", hint: "every paused session carries on", run: () => void everySession("resume") },
    { id: "fleet-answer-next", group: g, label: "Agents: answer next", hint: `${waiting} waiting · Attention, the oldest row`, run: () => (panels.update((p) => ({ attnSel: p.attention[0]?.id || "" })), goSection("agents"), setAttention(true)) },
    { id: "fleet-digest", group: g, label: "Agents: while you were away", hint: "what happened since you last looked (Live's inspector)", run: () => (void checkAway(true), openFleetLive()) },
    { id: "fleet-ollama", group: g, label: "Local: the Ollama steward", hint: "each host's card, models, findings and fit plan", run: () => openLocalHost() },
    { id: "fleet-who", group: g, label: "Agents: who can...", hint: "rank the fleet for a tool, an app, a skill, a model or a GPU", run: onLive(() => (openFleetLive(local()), setMachinePage("specs"))) },
  ];
  out.push(...missionCommands(g));
  for (const r of caps.get().rows || [])
    out.push({ id: "fleet-specs-" + r.harness, group: g, label: `Agents: specs of ${r.name}`, hint: r.summary || "its spec card", run: onLive(() => (openFleetLive(r.harness), setMachinePage("specs"))) });
  const sel = s.selected ? findAgent(s, s.selected) : null;
  if (sel) {
    const name = sel.a.name || sel.a.agent_id;
    out.push(
      { id: "fleet-steer", group: g, label: `Agents: steer ${name}`, hint: "the Steer box: a nudge or a new task", run: () => (openAgentPanel(sel.key), focusSteer("agent")) },
      { id: "fleet-pause", group: g, label: `Agents: ${sel.a.state === "paused" ? "resume" : "pause"} ${name}`, kbd: "P", run: () => void togglePause(sel.key) },
      { id: "fleet-stop", group: g, label: `Agents: stop ${name}`, hint: "asks first", run: () => askStop(sel.key) },
      { id: "fleet-takeover", group: g, label: `Agents: take over ${name}`, hint: "your brief replaces its task, recorded as a hand-off", run: () => askHandoff("take_over", sel.key) },
      { id: "fleet-handto", group: g, label: `Agents: hand ${name} to...`, hint: "another machine picks it up; it stops", run: () => askHandoff("hand_to", sel.key) },
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
  for (const h of s.harnesses.filter((x) => !x.local))
    out.push({ id: "fleet-kick-" + h.id, group: g, label: `Setup: forget ${h.name || h.id.slice(0, 8)}`, hint: "it leaves this hub; it pairs again with a new code", run: () => void kick(h.id, h.name || h.id) });
  return out;
}
