// The Mission panel's Start / list face (3.0.6.0 R8): "What should the
// fleet do?" (the goal), constraints, prefer (one chip per harness: click
// to put them in order; the planner breaks ties with it), a budget, and Plan
// it (`POST fleet/missions`: the hub's lead splits the goal by what every
// harness can do). Under it every mission, newest first: goal, state, parts
// by state, harnesses, cost, Open. With none yet, five lines on how it works.
import { useEffect, useRef, useState } from "react";
import { Button, Icon } from "../../lib/ui";
import { short } from "../orchestra/format";
import { useFleet } from "./store";
import { useMissions, usd, type Summary } from "./mstore";
import { openMission, planIt } from "./mload";

export const HOW: string[] = [
  "Say what the whole fleet should do, in one goal. The hub's lead splits it into parts.",
  "Each part goes to the harness that can do it: one that needs what only one harness has is pinned there, with the reason.",
  "The plan draws on the map, a node per part in its harness box. Drag a part to another box to move it; Approve when it reads right.",
  "Run starts the parts by their dependencies. A member's owner is asked first when it says ask; two parts that claim the same files run one after the other.",
  "The report says who did what on which harness, what it cost per harness, what was merged and what failed.",
];

function Prefer({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const harnesses = useFleet((s) => s.harnesses);
  const names = harnesses.map((h) => h.name || h.id.slice(0, 8));
  return (
    <div className="fmi-prefer" role="group" aria-label="Prefer these harnesses, in this order">
      {names.map((n) => {
        const at = value.indexOf(n);
        return (
          <button key={n} type="button" className="fmi-chip mono" aria-pressed={at >= 0} data-testid="fleet-mission-prefer" data-name={n}
                  title={at >= 0 ? `preferred ${at + 1}${at === 0 ? "st" : at === 1 ? "nd" : "th"}: click to take it out` : "click to prefer it (the order you click is the order of preference)"}
                  onClick={() => onChange(at >= 0 ? value.filter((x) => x !== n) : [...value, n])}>
            {at >= 0 && <b className="fmi-order">{at + 1}</b>}
            {n}
          </button>
        );
      })}
      {!names.length && <span className="muted">the harnesses show here once the fleet is read</span>}
    </div>
  );
}

function StateChip({ state }: { state: string }) {
  return <span className="og-chip mono fmi-state" data-state={state}>{state}</span>;
}

export function PartStates({ counts }: { counts: Record<string, number> }) {
  const keys = Object.keys(counts).filter((k) => counts[k]);
  return (
    <span className="fmi-pstates" data-testid="fleet-mission-pstates">
      {keys.map((k) => <span key={k} className="fmi-pstate mono" data-state={k} title={`${counts[k]} part${counts[k] === 1 ? "" : "s"} ${k}`}>{counts[k]} {k}</span>)}
    </span>
  );
}

function Row({ m }: { m: Summary }) {
  return (
    <li className="fmi-row" data-testid="fleet-mission-row" data-id={m.id} data-state={m.state}>
      <div className="fmi-row-top">
        <StateChip state={m.state} />
        <b className="fmi-goal" title={m.goal}>{short(m.goal, 90)}</b>
        <span className="spacer" />
        <span className="mono muted">{usd(m.cost_usd)}{m.budget_usd ? ` of ${usd(m.budget_usd)}` : ""}</span>
        <Button size="sm" variant="ghost" onClick={() => openMission(m.id)} data-testid="fleet-mission-open">Open</Button>
      </div>
      <div className="fmi-row-sub mono muted">
        <span>{m.id}</span> · <span>{m.parts} part{m.parts === 1 ? "" : "s"}</span> <PartStates counts={m.part_states || {}} />
        {m.harnesses.length > 0 && <> · <span>{m.harnesses.join(", ")}</span></>}
        {m.stop_reason && <> · <span title={m.stop_reason}>{short(m.stop_reason, 40)}</span></>}
      </div>
    </li>
  );
}

export function MissionStart() {
  const [goal, setGoal] = useState("");
  const [constraints, setConstraints] = useState("");
  const [prefer, setPrefer] = useState<string[]>([]);
  const [budget, setBudget] = useState("");
  const busy = useMissions((s) => s.busy === "plan");
  const problems = useMissions((s) => (s.open ? [] : s.problems));
  const list = useMissions((s) => s.list);
  const error = useMissions((s) => s.listError);
  const focus = useMissions((s) => s.newFocus);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (focus) window.setTimeout(() => box.current?.focus(), 120);
  }, [focus]);
  const go = async () => {
    if (!goal.trim() || busy) return;
    if (await planIt({ goal, constraints, prefer, budget_usd: budget })) setGoal("");
  };
  return (
    <div className="fmi-start" data-testid="fleet-mission-start">
      <form className="fmi-form" onSubmit={(e) => (e.preventDefault(), void go())}>
        <label className="fmi-field">
          <span className="rail-label mono">WHAT SHOULD THE FLEET DO?</span>
          <textarea ref={box} className="input fmi-goal-box" rows={2} value={goal} onChange={(e) => setGoal(e.target.value)} data-testid="fleet-mission-goal"
                    placeholder="One goal for every harness, e.g. scan the lab network, chart what it finds and link the chart from the docs"
                    onKeyDown={(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && (e.preventDefault(), void go())} />
        </label>
        <div className="fmi-form-row">
          <label className="fmi-field fmi-grow">
            <span className="rail-label mono">CONSTRAINTS</span>
            <input className="input" value={constraints} onChange={(e) => setConstraints(e.target.value)} placeholder="what every part must respect (optional)" data-testid="fleet-mission-constraints" />
          </label>
          <label className="fmi-field fmi-budget">
            <span className="rail-label mono">BUDGET $</span>
            <input className="input mono" inputMode="decimal" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="none" data-testid="fleet-mission-budget" />
          </label>
        </div>
        <div className="fmi-actions">
          <span className="rail-label mono" title="the planner breaks ties with this order">PREFER</span>
          <Prefer value={prefer} onChange={setPrefer} />
          <span className="spacer" />
          <Button type="submit" variant="primary" icon={<Icon name="send" />} disabled={!goal.trim() || busy} data-testid="fleet-mission-plan-it"
                  title="the hub's lead splits the goal into parts; nothing runs until you approve the plan">
            {busy ? "The lead is splitting it..." : "Plan it"}
          </Button>
        </div>
        {problems.length > 0 && <ul className="og-problems fmi-problems" data-testid="fleet-mission-problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
      </form>
      <section className="fmi-list-wrap" aria-label="Missions">
        <div className="rail-label mono">MISSIONS{list?.length ? ` · ${list.length}` : ""}</div>
        {!list ? <div className="og-wait mono muted">{error || "reading the missions..."}</div>
          : !list.length ? (
            <ol className="fl-explain fmi-how" data-testid="fleet-mission-how">
              {HOW.map((line, i) => <li key={line}><span className="fl-explain-n mono">{i + 1}</span><span>{line}</span></li>)}
            </ol>
          ) : <ul className="fmi-list" data-testid="fleet-mission-list">{list.map((m) => <Row key={m.id} m={m} />)}</ul>}
      </section>
    </div>
  );
}
