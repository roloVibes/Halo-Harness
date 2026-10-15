// The Mission panel's Running face (3.0.6.0 R8): every part by its state,
// live from the `mission` frames: asked = "waiting on <harness>'s owner"
// (an amber pulse: that member said ask, its owner has the card), running =
// the line its agent is on right now, read off the agent tree (the part runs
// as a `mission-worker` session whose row names the mission and the part),
// then done / failed / stopped / skipped. The cost per harness ticks up; the
// merge queue shows the order, what merged and the conflicts the judge
// settled. Stop asks for a reason; "Open the part's agent" selects it on the
// map and in the Agent panel.
import { Button, Icon } from "../../lib/ui";
import { cost, short } from "../orchestra/format";
import { openAgentPanel, select } from "./actions";
import { useTicker } from "./MapNode";
import { missions, partMotion, partState, useMissions, usd, type PlanPart, type View } from "./mstore";
import { keyOf, useFleet } from "./store";
import type { AgentRow, Harness } from "./types";

type Live = { key: string; agent: AgentRow };

/** The part's session on its harness (its registry row carries `mission` and `part`) and its main agent. */
export function partAgent(harnesses: Harness[], mid: string, pid: string, hid?: string | null): Live | null {
  for (const h of harnesses) {
    if (hid && h.id !== hid) continue;
    for (const s of h.sessions || []) {
      if (s.mission !== mid || String(s.part) !== String(pid)) continue;
      const main = (s.agents || []).find((a) => !a.parent) || s.agents?.[0];
      if (main) return { key: keyOf(h.id, s.session_id, main.agent_id), agent: main };
    }
  }
  return null;
}

function lineOf(a: AgentRow): string {
  return String(a.current || (a.state === "running" ? "thinking" : a.last_text) || a.task || a.state || "");
}

function PartLine({ p, v }: { p: PlanPart; v: View }) {
  const harnesses = useFleet((s) => s.harnesses);
  const run = v.mission.parts?.[p.id];
  const st = partState(v, p.id);
  const who = run?.harness_name || p.harness_name || "its harness";
  const live = partAgent(harnesses, v.mission.id, p.id, run?.harness || p.harness);
  const now = st === "asked" ? `waiting on ${who}'s owner to allow it`
    : st === "running" ? (live ? lineOf(live.agent) : "starting its session...")
    : st === "pending" ? `waits for ${p.depends_on.length ? "part " + p.depends_on.join(", ") : "a free slot"}`
    : run?.error ? `${st}: ${run.error}` : st;
  return (
    <li className="fmi-live" data-testid="fleet-mission-live" data-part={p.id} data-state={st} data-motion={partMotion(st)}>
      <span className="fmi-live-dot" aria-hidden="true" />
      <span className="mono fmi-pid">{p.id}</span>
      <div className="fmi-live-main">
        <div><b>{short(p.title, 56)}</b> <span className="muted mono">on {who}</span></div>
        <div className="fmi-live-now mono" data-testid="fleet-mission-now" title={now}>{short(now, 110)}</div>
      </div>
      <span className="fmi-pstate mono" data-state={st}>{st}</span>
      <span className="mono fmi-small">{cost(run?.cost_usd || 0)}</span>
      {live && (
        <Button size="sm" variant="ghost" icon={<Icon name="agent" />} data-testid="fleet-mission-open-agent" title="select it on the map and open it in the Agent panel"
                onClick={() => (select(live.key), openAgentPanel(live.key))}>Open the part's agent</Button>
      )}
    </li>
  );
}

function HarnessCost({ name, usdNow }: { name: string; usdNow: number }) {
  const shown = useTicker(usdNow);
  return <li className="fmi-hcost" data-testid="fleet-mission-hcost" data-name={name}><span>{name}</span><b className="mono">{usd(shown)}</b></li>;
}

function MergeQueue({ v }: { v: View }) {
  const order = v.plan?.merge_order || [];
  const m = v.mission.merge;
  if (!order.length) return <p className="muted fmi-small">No repo part: nothing to merge; each part's files land in the mission folder.</p>;
  return (
    <ol className="fmi-merge" data-testid="fleet-mission-merge">
      {order.map((pid) => {
        const merged = !!m?.merged.includes(pid);
        const skipped = m?.skipped.find((x) => x.part === pid);
        const judged = (m?.conflicts || []).filter((c) => c.part === pid);
        return (
          <li key={pid} data-merged={merged || undefined}>
            <span className="mono">part {pid}</span>{" "}
            <span className="fmi-pstate mono" data-state={merged ? "merged" : skipped ? "skipped" : "pending"}>{merged ? "merged" : skipped ? "skipped" : v.mission.state === "merging" ? "in the queue" : "waits"}</span>
            {judged.map((c) => <span key={c.file} className="og-chip mono fmi-dep" data-seq title={`${c.hunks} hunks judged${c.tests_ok === false ? ", tests failed" : ""}`}>{c.file} judged</span>)}
            {skipped && <span className="muted"> {skipped.why}</span>}
          </li>
        );
      })}
      {m?.branch && <li className="muted mono">into {m.branch}{m.finished ? ` at ${m.finished.slice(0, 8)}` : ""}</li>}
    </ol>
  );
}

export function MissionRun() {
  const v = useMissions((s) => s.view);
  const busy = useMissions((s) => s.busy);
  if (!v) return null;
  const parts = v.plan?.parts || [];
  const per = new Map<string, number>();
  for (const p of parts) {
    const run = v.mission.parts?.[p.id];
    const name = run?.harness_name || p.harness_name || "no harness";
    per.set(name, (per.get(name) || 0) + (Number(run?.cost_usd) || 0));
  }
  const live = ["running", "merging"].includes(v.mission.state);
  return (
    <div className="fmi-run" data-testid="fleet-mission-run-face">
      <ul className="fmi-lives">{parts.map((p) => <PartLine key={p.id} p={p} v={v} />)}</ul>
      <div className="fmi-run-side">
        <section>
          <div className="rail-label mono">COST PER HARNESS</div>
          <ul className="fmi-hcosts">{[...per.entries()].map(([n, c]) => <HarnessCost key={n} name={n} usdNow={c} />)}</ul>
        </section>
        <section>
          <div className="rail-label mono">MERGE QUEUE</div>
          <MergeQueue v={v} />
        </section>
      </div>
      {live && (
        <div className="fmi-actions">
          <Button variant="danger" icon={<Icon name="stop" />} disabled={!!busy} onClick={() => missions.update(() => ({ stopAsk: true }))} data-testid="fleet-mission-stop">
            {busy === "stop" ? "Stopping..." : "Stop the mission..."}
          </Button>
          <span className="muted fmi-hint">every running part is asked to stop; what is done stays done</span>
        </div>
      )}
    </div>
  );
}
