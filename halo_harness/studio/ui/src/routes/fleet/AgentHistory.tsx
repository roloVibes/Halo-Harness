// The agent panel's extras (3.0.5.0 R4): under the controls, Take over,
// Hand to..., Record (this agent as one HTML file) and Replay (its session
// on the Roles canvas); and when no agent is picked, this harness's last
// sessions (`GET fleet/history?role=main`) with Replay and Record, so a
// finished session can be played back even when nothing is live.
import { useEffect } from "react";
import { api } from "../../lib/api";
import { Button, Icon } from "../../lib/ui";
import { short } from "../orchestra/format";
import { askHandoff, record } from "./extras";
import { age, panels, usePanels, type Run } from "./pstore";
import { openReplay } from "./replay";
import { keyOf, localId, useFleet } from "./store";
import type { AgentRef } from "./types";

export function AgentExtras({ r, done, noControl }: { r: AgentRef; done: boolean; noControl: boolean }) {
  const why = noControl ? `${r.h.name || "that harness"} takes no commands from here` : done ? "it has finished" : undefined;
  return (
    <div className="fa-extras" data-testid="fleet-agent-extras">
      <Button size="sm" variant="ghost" icon={<Icon name="send" />} disabled={done || noControl} title={why || "give it a new brief, recorded as a hand-off"} onClick={() => askHandoff("take_over", r.key)} data-testid="fleet-takeover-open">
        Take over
      </Button>
      <Button size="sm" variant="ghost" icon={<Icon name="link" />} disabled={done || noControl} title={why || "another harness picks it up; this one stops"} onClick={() => askHandoff("hand_to", r.key)} data-testid="fleet-handto-open">
        Hand to...
      </Button>
      <Button size="sm" variant="ghost" icon={<Icon name="file" />} title="this agent as one HTML file you can replay anywhere" onClick={() => void record(r.key, true)} data-testid="fleet-record">
        Record
      </Button>
      {r.h.local && (
        <Button size="sm" variant="ghost" icon={<Icon name="play" />} title="play its session back on the Roles canvas" onClick={() => void openReplay(r.s.session_id, "local")} data-testid="fleet-replay">
          Replay
        </Button>
      )}
    </div>
  );
}

async function loadHistory(): Promise<void> {
  try {
    const r = await api.get<{ runs: Run[] }>("fleet/history", { role: "main", n: 8 });
    panels.update(() => ({ history: r.runs || [] }));
  } catch {
    panels.update(() => ({ history: [] }));
  }
}

export function RecentSessions() {
  const runs = usePanels((s) => s.history);
  const here = useFleet((s) => localId(s));
  useEffect(() => void loadHistory(), []);
  if (!runs?.length) return null;
  return (
    <section className="fa-history" data-testid="fleet-agent-history">
      <div className="rail-label mono">LAST SESSIONS ON THIS HARNESS</div>
      <ul>
        {runs.map((r) => (
          <li key={r.session_id} data-testid="fleet-history-run">
            <span className="mono muted">{age(r.finished || r.started || 0)} ago</span>
            <span className="fa-history-task">{short(r.task || r.session_id, 60)}</span>
            <span className="spacer" />
            <button className="og-link mono" onClick={() => void openReplay(r.session_id, "local")} data-testid="fleet-history-replay">replay</button>
            {here && <button className="og-link mono" onClick={() => void record(keyOf(here, r.session_id, "main"), false)}>record</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}
