// The palette's Fleet group: pair a harness, kick a member, group the map
// by project, follow / steer / pause / stop the selected agent, follow any
// live agent by name, pause all, resume all, and open the selected session
// in Orchestra or Flow when it is one.
import { goSection } from "../../lib/store";
import { askStop, everySession, kick, openAgentPanel, select, toggleByProject, toggleFollow, togglePause } from "./actions";
import { allAgents, enterWorkspace, fleet, findAgent, isLive, sessionTitle } from "./store";
import { startFleet } from "./sync";

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
  ];
  const sel = s.selected ? findAgent(s, s.selected) : null;
  if (sel) {
    const name = sel.a.name || sel.a.agent_id;
    out.push(
      { id: "fleet-steer", group: g, label: `Fleet: steer ${name}`, hint: "the Steer box: a nudge or a new task", run: inFleet(() => (openAgentPanel(), fleet.update((st) => ({ steerFocus: st.steerFocus + 1 })))) },
      { id: "fleet-pause", group: g, label: `Fleet: ${sel.a.state === "paused" ? "resume" : "pause"} ${name}`, kbd: "P", run: () => void togglePause(sel.key) },
      { id: "fleet-stop", group: g, label: `Fleet: stop ${name}`, hint: "asks first", run: () => askStop(sel.key) },
    );
    if (sel.s.kind === "orchestra-worker") out.push({ id: "fleet-orchestra", group: g, label: "Fleet: open this session in Orchestra", run: () => goSection("orchestra") });
    if (sel.s.kind === "flow") out.push({ id: "fleet-flow", group: g, label: "Fleet: open this session in Flow", run: () => goSection("flow") });
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
