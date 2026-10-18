// A bio's schedule and triggers (3.1.1.0 R3; the sections agents_yaml.py
// validates since 2.0.5): the schedule fires the agent on a cron expression
// or every N minutes with its prompt (and, optionally, its own model); each
// trigger starts it once per file change, halo event or message from a role.
// They fire only while a session that loaded the agent's lineup is alive.
import { useMemo } from "react";
import { Button } from "../../lib/ui";
import { useHelpGroup } from "../../lib/fieldHelp";
import { editBio, setKey } from "./bioActions";
import { at, Sec } from "./BioFields";
import { ListIn, Pick, Row, TextIn } from "./controls";
import { useRoles } from "./store";
import type { Raw } from "./types";

const KINDS = ["file_change", "event", "message"];
type Trigger = Raw & { on?: string };

function putTriggers(next: Trigger[]): void {
  editBio((r) => setKey(r, "triggers", next.length ? next : undefined));
}

function TriggerRow({ t, i, all }: { t: Trigger; i: number; all: Trigger[] }) {
  const set = (key: string, v: unknown) => {
    const next = all.map((x) => ({ ...x }));
    if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) delete next[i][key];
    else next[i][key] = v;
    putTriggers(next);
  };
  const on = String(t.on || "file_change");
  return (
    <div className="re-row rb-trigger" data-testid="bio-trigger" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1.4fr) minmax(0,1.4fr) 28px" }}>
      <Pick value={on} options={KINDS} onChange={(v) => set("on", v)} />
      {on === "file_change" ? (
        <ListIn value={Array.isArray(t.paths) ? (t.paths as string[]) : []} placeholder="src/**/*.py" onCommit={(v) => set("paths", v)} hint="" />
      ) : on === "event" ? (
        <TextIn value={String(t.name ?? "")} placeholder="a halo event kind" onCommit={(v) => set("name", v.trim())} />
      ) : (
        <TextIn value={String(t.from ?? "")} placeholder="a role or alias" onCommit={(v) => set("from", v.trim())} />
      )}
      <TextIn value={String(t.prompt ?? "")} placeholder="prompt (optional)" onCommit={(v) => set("prompt", v.trim())} />
      <button className="icon-btn" title="Remove this trigger" aria-label="Remove this trigger" onClick={() => putTriggers(all.filter((_x, j) => j !== i))}>×</button>
    </div>
  );
}

export function BioSchedule({ d }: { d: Raw }) {
  const h = useHelpGroup("bio");
  const catalog = useRoles((s) => s.models);
  const refs = useMemo(() => catalog.map((m) => m.ref), [catalog]);
  const sch = (d.schedule && typeof d.schedule === "object" && !Array.isArray(d.schedule) ? d.schedule : {}) as Raw;
  const triggers = (Array.isArray(d.triggers) ? d.triggers : []) as Trigger[];
  return (
    <>
      <Sec title="SCHEDULE">
        <TextIn label="Cron" hint={h["schedule.cron"]} placeholder="0 9 * * 1-5" value={String(sch.cron ?? "")} onCommit={(v) => at("schedule", "cron")(v.trim())} testid="bio-schedule-cron" />
        <TextIn label="Every" hint={h["schedule.every"]} placeholder="30m" value={String(sch.every ?? "")} onCommit={(v) => at("schedule", "every")(v.trim())} testid="bio-schedule-every" />
        <TextIn label="Prompt" area hint={h["schedule.prompt"]} value={String(sch.prompt ?? "")} onCommit={at("schedule", "prompt")} testid="bio-schedule-prompt" />
        <Pick label="Model" hint={h["schedule.model"]} value={String(sch.model ?? "")} options={["", ...refs]} onChange={at("schedule", "model")} />
      </Sec>
      <Sec title="TRIGGERS">
        <Row hint={h.triggers}>
          <div className="re-rows" data-testid="bio-triggers">
            {triggers.map((t, i) => <TriggerRow key={i} t={t} i={i} all={triggers} />)}
            <Button size="sm" variant="ghost" onClick={() => putTriggers([...triggers, { on: "file_change", paths: [] }])} data-testid="bio-trigger-add">Add a trigger</Button>
          </div>
        </Row>
      </Sec>
    </>
  );
}
