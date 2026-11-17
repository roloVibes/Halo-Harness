// Agents' tab switch (3.6.0.2 R52: four tabs and nothing else): 1 · Agents | 2 · Workflows | 3 · Map | 4 · Live, keys 1 2 3
// 4. Each tab draws it first in its own view bar; the Live tab carries a dot while a session runs (a run is Live's; Map is
// the plan). An old door's one line (Note) shows beside it the first time it brought this browser here.
import type { AgentsView } from "../../lib/agentsDoor";
import { useStore } from "../../lib/store";
import { agents, dismissNote, setAgentsView } from "./store";
import { useRunning } from "../crew/map/litStore";
import { WORDS } from "../crew/map/truth";

const VIEWS: [AgentsView, string, string, string][] = [
  ["crew", "1 · Agents", "1", "Make an agent: its name, what it does, its model, what it may use, how careful; try it, save it"], // 3.6.0.0 R1
  ["workflows", "2 · Workflows", "2", "Make a workflow: your agents in steps, in order; try it, save it"], // 3.6.0.0 R2
  ["map", "3 · Map", "3", "Connect them: who main hands work to, and when; the map your sessions run on"], // 3.6.0.0 R3
  ["live", `4 · ${WORDS.live}`, "4", "What a session is doing now, drawn on the map it really follows"], // 3.6.0.2 R52, section 4
];

export function ViewSwitch({ view }: { view: AgentsView }) {
  const runs = useRunning().length > 0; // R52: the Live tab shows a dot while a session runs
  return (
    <>
    <span className="segmented ag-views" role="tablist" aria-label="Agents: Agents, Workflows, Map or Live" data-testid="agents-views">
      {VIEWS.map(([v, label, key, title]) => (
        <button key={v} role="tab" className={view === v ? "on" : ""} aria-selected={view === v} aria-pressed={view === v}
                title={`${title} (${key})${v === "live" && runs ? " -- a session is running" : ""}`} onClick={() => setAgentsView(v)}
                data-testid={`agents-view-${v}`} data-view={v} data-running={v === "live" && runs ? "1" : undefined}>
          {label}
        </button>
      ))}
    </span>
    <Note />
    </>
  );
}

export function Note() {
  const note = useStore(agents, (s) => s.note);
  if (!note) return null;
  const shown = note;
  return (
    <span className="ag-note mono" data-testid="agents-team-note">
      <span className="ag-note-text" title={shown}>{shown}</span>
      <button className="icon-btn ag-note-x" onClick={dismissNote} aria-label="Dismiss" title="Dismiss this line">×</button>
    </span>
  );
}
