// Agents' bar (3.3.16.0 R1): the view switch first -- Cast | Runs | Live (C, R, L) -- then what the view adds: on Runs,
// Test this lineup (TestLineup.tsx); Team's one line the first time `?mode=team` brought this browser here. The bar is
// 40 px and quiet: nothing on it opens anything on its own. 3.3.16.0 R2: the Attention chip at its right end, in every
// view (AttentionChip.tsx: the fleet's queue, amber while anything waits on you).
import type { AgentsView } from "../../lib/agentsDoor";
import { useStore } from "../../lib/store";
import { agents, dismissNote, setAgentsView } from "./store";
import { TestLineup } from "./runs/TestLineup";
import { AttentionChip } from "./AttentionChip";
import { LibraryButton } from "./workflows/Library";

const VIEWS: [AgentsView, string, string, string][] = [
  ["cast", "Cast", "C", "The lineup and its bios: every card, its model and its tier"],
  ["runs", "Runs", "R", "Give the lineup a goal: the lead's plan, the lanes, the merge, the tests, the report"],
  ["live", "Live", "L", "What runs now: this halo's session, or every machine of the fleet, as a tree"],
  ["workflows", "Workflows", "W", "The squares main may hand work to: one card per enabled workflow, its contract on the card"],
];

export function ViewSwitch({ view }: { view: AgentsView }) {
  return (
    <span className="segmented ag-views" role="tablist" aria-label="Agents: Cast, Runs, Live or Workflows" data-testid="agents-views">
      {VIEWS.map(([v, label, key, title]) => (
        <button key={v} role="tab" className={view === v ? "on" : ""} aria-selected={view === v} aria-pressed={view === v}
                title={`${title} (${key})`} onClick={() => setAgentsView(v)} data-testid={`agents-view-${v}`} data-view={v}>
          {label}
        </button>
      ))}
    </span>
  );
}

function Note() {
  const note = useStore(agents, (s) => s.note);
  if (!note) return null;
  return (
    <span className="ag-note mono" data-testid="agents-team-note">
      {note}
      <button className="icon-btn ag-note-x" onClick={dismissNote} aria-label="Dismiss" title="Dismiss this line">×</button>
    </span>
  );
}

export function AgentsBar({ view }: { view: AgentsView }) {
  return (
    <div className="ag-bar" data-testid="agents-bar" data-density="bar">
      <ViewSwitch view={view} />
      {view === "runs" && <TestLineup />}
      {(view === "workflows" || view === "cast") && <LibraryButton plus />}
      <Note />
      <span className="spacer" />
      <AttentionChip />
    </div>
  );
}
