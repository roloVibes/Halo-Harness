// fleet-activity: what the whole fleet does, as it happens. On top the
// timeline strip (Timeline.tsx: one lane per live agent); under it the
// merged live log of every harness, session and agent: state changes, tool
// calls, the text they write (joined into one line per burst), the cards
// they open, errors, harnesses joining and leaving. Filters by harness,
// session, agent and kind; Follow keeps the newest line in view; a click on
// a line selects that agent on the map.
import { useEffect, useMemo, useRef } from "react";
import { Button, Icon } from "../../lib/ui";
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { clock, short } from "../orchestra/format";
import { select } from "./actions";
import { panels, usePanels, type Filter, type LogLine } from "./pstore";
import { allAgents, sessionTitle, useCounts, useFleet } from "./store";
import { Timeline } from "./Timeline";

const KINDS = ["state", "tool", "text", "ask", "error", "fleet"];

function Pick({ label, field, options }: { label: string; field: keyof Filter; options: [string, string][] }) {
  const value = usePanels((s) => s.filter[field]);
  return (
    <label className="fac-pick" title={`only this ${label}`}>
      <select value={value} aria-label={label} onChange={(e) => panels.update((s) => ({ filter: { ...s.filter, [field]: e.target.value } }))} data-testid={`fleet-filter-${field}`}>
        <option value="">every {label}</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

function Filters() {
  const harnesses = useFleet((s) => s.harnesses);
  const follow = usePanels((s) => s.logFollow);
  const refs = useMemo(() => allAgents({ harnesses } as never), [harnesses]);
  const sessions = harnesses.flatMap((h) => h.sessions.map((s) => [s.session_id, `${h.name || h.id.slice(0, 6)} · ${short(sessionTitle(s), 30)}`] as [string, string]));
  const agents = refs.map((r) => [r.a.agent_id + "@" + r.s.session_id, `${r.a.name || r.a.agent_id} · ${short(sessionTitle(r.s), 20)}`] as [string, string]);
  return (
    <div className="fac-filters">
      <Pick label="harness" field="harness" options={harnesses.map((h) => [h.id, h.name || h.id.slice(0, 8)])} />
      <Pick label="session" field="session" options={sessions} />
      <Pick label="agent" field="agent" options={agents} />
      <Pick label="kind" field="kind" options={KINDS.map((k) => [k, k])} />
      <span className="spacer" />
      <Button size="sm" variant={follow ? "primary" : "ghost"} icon={<Icon name="follow" />} aria-pressed={follow} onClick={() => panels.update((s) => ({ logFollow: !s.logFollow }))}>
        Follow
      </Button>
    </div>
  );
}

const keep = (f: Filter) => (l: LogLine) =>
  (!f.harness || l.harness === f.harness) && (!f.session || l.session_id === f.session) && (!f.agent || `${l.agent_id}@${l.session_id}` === f.agent) && (!f.kind || l.kind === f.kind);

export function ActivityDetail() {
  const log = usePanels((s) => s.log);
  const filter = usePanels((s) => s.filter);
  const follow = usePanels((s) => s.logFollow);
  const harnesses = useFleet((s) => s.harnesses);
  const box = useRef<HTMLDivElement>(null);
  const shown = useMemo(() => log.filter(keep(filter)), [log, filter]);
  const names = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of allAgents({ harnesses } as never)) m.set(r.key, `${r.h.name || r.h.id.slice(0, 6)} · ${r.a.name || r.a.agent_id}`);
    for (const h of harnesses) m.set(`${h.id}||`, h.name || h.id.slice(0, 8));
    return m;
  }, [harnesses]);
  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [shown, follow]);
  return (
    <div className="fac" data-testid="fleet-activity-detail">
      <Timeline />
      <Filters />
      <div className="fac-log" ref={box} data-testid="fleet-log">
        {!shown.length && <p className="muted fac-none">{log.length ? "Nothing matches these filters." : "The fleet's live log starts here: state changes, tool calls, text, cards and errors as they arrive."}</p>}
        {shown.map((l) => (
          <div key={l.n} className="fac-line" data-kind={l.kind} data-testid="fleet-log-line" onClick={() => l.session_id && select(l.key)} title={l.session_id ? "select this agent on the map" : undefined}>
            <span className="mono fac-ts">{clock(l.ts / 1000)}</span>
            <span className="mono fac-kind">{l.kind}</span>
            <span className="fac-who mono">{names.get(l.key) || l.key.split("|")[2] || ""}</span>
            <span className="fac-text">{l.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ActivityGlance() {
  const c = useCounts();
  const last = usePanels((s) => s.log[s.log.length - 1]);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={c.live} label="agents live" tone={c.live ? "accent" : undefined} />
      </div>
      <div className="glance-hint mono">{last ? short(last.text, 80) : "Expand for the timeline and the live log."}</div>
    </div>
  );
}

export function useActivityMotion(): MotionState {
  const c = useCounts();
  return c.live ? "working" : "idle";
}
