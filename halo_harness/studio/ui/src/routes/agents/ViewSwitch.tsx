// Agents' tab switch (3.6.0.0 R5: three tabs and nothing else): 1 · Agents | 2 · Workflows | 3 · Map, keys 1 2 3. Each
// tab draws it first in its own view bar; the Map tab carries a dot while a session runs on a map. An old door's one
// line (Note) shows beside it the first time it brought this browser here.
import type { AgentsView } from "../../lib/agentsDoor";
import { useStore } from "../../lib/store";
import { agents, dismissNote, setAgentsView } from "./store";
import { useRunning } from "../crew/map/litStore";

const VIEWS: [AgentsView, string, string, string][] = [
  ["crew", "1 · Agents", "1", "Make an agent: its name, what it does, its model, what it may use, how careful; try it, save it"], // 3.6.0.0 R1
  ["workflows", "2 · Workflows", "2", "Make a workflow: your agents in steps, in order; try it, save it"], // 3.6.0.0 R2
  ["map", "3 · Map", "3", "Connect them: who main hands work to, and when; the map your sessions run on"], // 3.6.0.0 R3
];

export function ViewSwitch({ view }: { view: AgentsView }) {
  const onMap = useRunning().some((s) => !!s.map); // 3.6.0.0 R4: the Map tab shows a dot while a session runs on a map
  return (
    <>
    <span className="segmented ag-views" role="tablist" aria-label="Agents: Agents, Workflows or Map" data-testid="agents-views">
      {VIEWS.map(([v, label, key, title]) => (
        <button key={v} role="tab" className={view === v ? "on" : ""} aria-selected={view === v} aria-pressed={view === v}
                title={`${title} (${key})${v === "map" && onMap ? " -- a session is running on a map" : ""}`} onClick={() => setAgentsView(v)}
                data-testid={`agents-view-${v}`} data-view={v} data-running={v === "map" && onMap ? "1" : undefined}>
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
