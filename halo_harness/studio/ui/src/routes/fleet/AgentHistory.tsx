// The agent panel's extras (3.0.5.0 R4): under the controls, Take over, Hand to... and Record (this session as one
// HTML page); and when no agent is picked, this harness's last sessions (`GET live/history?role=main`, the last 8), each
// with "export" (3.6.0.3 B, Z9: that session's Markdown export, TraceExport's own fetch-and-save, the same bytes as
// Session -> Feed -> Export) and "record". An older session is exported from the terminal (`halo session export <id>`).
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Button, Icon } from "../../lib/ui";
import { short } from "../orchestra/format";
import { askHandoff, record } from "./extras";
import { age, panels, usePanels, type Run } from "./pstore";
import { exportTrace } from "../session/TraceExport";
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
      <Button size="sm" variant="ghost" icon={<Icon name="file" />} title="this session as one HTML page you can open anywhere" onClick={() => void record(r.key, true)} data-testid="fleet-record">
        Record
      </Button>
    </div>
  );
}

async function loadHistory(): Promise<void> {
  try {
    const r = await api.get<{ runs: Run[] }>("live/history", { role: "main", n: 8 });
    panels.update(() => ({ history: r.runs || [] }));
  } catch {
    panels.update(() => ({ history: [] }));
  }
}

export function RecentSessions() {
  const runs = usePanels((s) => s.history);
  const here = useFleet((s) => localId(s));
  const [busy, setBusy] = useState(""); // the session being saved; its toast says what was saved, or why not
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
            <button className="og-link mono" disabled={!!busy} onClick={() => (setBusy(r.session_id), void exportTrace(r.session_id).finally(() => setBusy("")))} data-testid="fleet-history-export" title="this session as one Markdown file: every prompt, reply and tool call, keys masked">export</button>
            {here && <button className="og-link mono" title="this session as one HTML page you can open anywhere" onClick={() => void record(keyOf(here, r.session_id, "main"), false)}>record</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}
