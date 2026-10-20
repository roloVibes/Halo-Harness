// The palette's Fleet group: pair a harness, kick a member, group the map
// by project, follow / steer / pause / stop the selected agent, follow any
// live agent by name, pause all, resume all, and open the selected session
// in Orchestra when it is one. R4: answer next (Attention, the oldest
// row), record, take over, hand to, replay the selected session, the digest.
// R6: who can... (the Capabilities panel's search) and the specs of each harness.
// R8: new mission, approve mission, stop mission, mission report.
import { goSection } from "../../lib/store";
import { askStop, everySession, kick, openAgentPanel, select, toggleByProject, toggleFollow, togglePause } from "./actions";
import { allAgents, enterWorkspace, fleet, findAgent, isLive, sessionTitle } from "./store";
import { checkAway } from "./Digest";
import { askHandoff, record, showFleetPanel } from "./extras";
import { panels } from "./pstore";
import { openReplay } from "./replay";
import { startFleet } from "./sync";
import { askWho } from "./Capabilities";
import { caps, focusHarness } from "./caps";
import { missionCommands } from "./mcommands";
import { focusSteer } from "./Steer";

export type FleetCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

function inFleet(fn: () => void): () => void {
  return () => {
    goSection("fleet");
    startFleet();
    enterWorkspace();
    window.setTimeout(fn, 80);
  };
}

export function fleetCommands(): FleetCommand[] {
  const s = fleet.get();
  const g = "Fleet";
  const out: FleetCommand[] = [
    { id: "fleet-pair", group: g, label: "Fleet: pair a harness", hint: "a one-time six-word code and its QR for another machine", run: inFleet(() => fleet.update(() => ({ pairOpen: true }))) },
    { id: "fleet-by-project", group: g, label: s.byProject ? "Fleet: group the map by harness" : "Fleet: group the map by project", hint: "one box per repo, the harness colour on each card", run: inFleet(toggleByProject) },
    { id: "fleet-follow", group: g, label: s.follow ? "Fleet: stop following the agent" : "Fleet: follow the agent", hint: "the stream scrolls with it", kbd: "F", run: toggleFollow },
    { id: "fleet-pause-all", group: g, label: "Fleet: pause all", hint: "every session holds at its next tool or model call", run: () => void everySession("pause") },
    { id: "fleet-resume-all", group: g, label: "Fleet: resume all", hint: "every paused session carries on", run: () => void everySession("resume") },
    { id: "fleet-answer-next", group: g, label: "Fleet: answer next", hint: `${panels.get().attention.length} waiting · Attention, the oldest row`, run: inFleet(() => (panels.update((p) => ({ attnSel: p.attention[0]?.id || "" })), showFleetPanel("fleet-attention"))) },
    { id: "fleet-digest", group: g, label: "Fleet: while you were away", hint: "what happened since you last looked", run: () => void checkAway(true) },
    { id: "fleet-who", group: g, label: "Fleet: who can...", hint: "rank the fleet for a tool, an app, a skill, a model or a GPU", run: inFleet(() => (showFleetPanel("fleet-capabilities"), askWho())) },
  ];
  out.push(...missionCommands(g, inFleet));
  for (const r of caps.get().rows || [])
    out.push({ id: "fleet-specs-" + r.harness, group: g, label: `Fleet: specs of ${r.name}`, hint: r.summary || "its spec card", run: inFleet(() => focusHarness(r.harness, "fleet-capabilities")) });
  const sel = s.selected ? findAgent(s, s.selected) : null;
  if (sel) {
    const name = sel.a.name || sel.a.agent_id;
    out.push(
      { id: "fleet-steer", group: g, label: `Fleet: steer ${name}`, hint: "the Steer box: a nudge or a new task", run: inFleet(() => (openAgentPanel(), focusSteer("agent"))) },
      { id: "fleet-pause", group: g, label: `Fleet: ${sel.a.state === "paused" ? "resume" : "pause"} ${name}`, kbd: "P", run: () => void togglePause(sel.key) },
      { id: "fleet-stop", group: g, label: `Fleet: stop ${name}`, hint: "asks first", run: () => askStop(sel.key) },
      { id: "fleet-takeover", group: g, label: `Fleet: take over ${name}`, hint: "your brief replaces its task, recorded as a hand-off", run: () => askHandoff("take_over", sel.key) },
      { id: "fleet-handto", group: g, label: `Fleet: hand ${name} to...`, hint: "another harness picks it up; it stops", run: () => askHandoff("hand_to", sel.key) },
      { id: "fleet-record", group: g, label: `Fleet: record ${name}`, hint: "one HTML file that replays anywhere", run: () => void record(sel.key, true) },
    );
    if (sel.h.local) out.push({ id: "fleet-replay", group: g, label: "Fleet: replay this session on the Roles canvas", hint: "the cards light up in the order they worked", run: () => void openReplay(sel.s.session_id, "local") });
    if (sel.s.kind === "orchestra-worker") out.push({ id: "fleet-orchestra", group: g, label: "Fleet: open this session in Orchestra", run: () => goSection("orchestra") });
  }
  for (const r of allAgents(s).filter((x) => isLive(x.a)).slice(0, 24))
    out.push({
      id: "fleet-agent-" + r.key,
      group: g,
      label: `Fleet: follow agent ${r.a.name || r.a.agent_id}`,
      hint: `${r.a.state} · ${r.h.name || ""} · ${sessionTitle(r.s)}`,
      run: inFleet(() => (select(r.key), openAgentPanel())),
    });
  for (const h of s.harnesses.filter((x) => !x.local))
    out.push({ id: "fleet-kick-" + h.id, group: g, label: `Fleet: kick ${h.name || h.id.slice(0, 8)}`, hint: "it leaves this hub; it pairs again with a new code", run: () => void kick(h.id, h.name || h.id) });
  return out;
}
