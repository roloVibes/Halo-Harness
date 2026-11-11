// A goal run in Live's inspector (3.4.0.0 D "the runs fold"; R1b's rule: summary first, then one block per page). A
// lane picked on the canvas: its goal, what it owns, its state, its last output, its cost and model; a lead: the goal,
// done when, the state, the lanes by state, the cost, the gate's test. Then one Open row per page -- Plan, Claims, Diff,
// Test result, Log (RunPages.tsx) -- each its own page with Back (or Esc). The controls a run takes are here: Stop the
// run (asks the runner to stop at its next step, after one confirm), Review the plan while it waits on you, Steer
// (the lane's worker: its agent in this inspector, where Steer, Pause and Stop are), Watch in Session; the claims page
// releases or steals a claim. Nothing here opens on its own.
import { useState, type KeyboardEvent } from "react";
import { Button } from "../../../lib/ui";
import { cost, short } from "../../orchestra/format";
import { LANE_LABEL, useOrch } from "../../orchestra/store";
import { stopRun } from "../../orchestra/sync";
import type { Lane, RunPayload } from "../../orchestra/types";
import { useFleet } from "../../fleet/store";
import { runSession, WatchInSession } from "../../session/Watch";
import { clearPick, pickLive, setMachinePage, useMachinePage } from "../live/scope";
import { ownsOf } from "./Owns";
import { reviewPlan } from "./planPanel";
import { ClaimsPage, DiffPage, LogPage, PAGES, PlanPage, TestPage, type RunPage } from "./RunPages";

function Stop({ run }: { run: string }) {
  const [ask, setAsk] = useState(false);
  if (!ask) return <Button size="sm" variant="danger" onClick={() => setAsk(true)} data-testid="run-stop" title="Ask the runner to stop at its next step (one confirm first)">Stop the run</Button>;
  return (
    <span className="ri-confirm" data-testid="run-stop-confirm">
      <span className="mono">Stop run {run} at its next step?</span>
      <Button size="sm" variant="danger" onClick={() => (setAsk(false), void stopRun())} data-testid="run-stop-yes">Stop</Button>
      <Button size="sm" variant="ghost" onClick={() => setAsk(false)} data-testid="run-stop-no">Keep it running</Button>
    </span>
  );
}

/** The lane's worker as a live agent of this harness (its holder's session), for Steer; '' when it has none yet. */
function useWorkerKey(lane: Lane | null): string {
  return useFleet((s) => {
    const sid = String(lane?.holder || "").split("/")[0];
    if (!lane || !sid) return "";
    const h = s.harnesses.find((x) => x.local);
    const sess = h?.sessions?.find((x) => x.session_id === sid);
    const root = sess?.agents?.find((a) => !a.parent) || sess?.agents?.[0];
    return h && sess && root ? `${h.id}|${sid}|${root.agent_id}` : "";
  });
}

function Facts({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="ri-facts mono" data-testid="run-summary-facts">
      {rows.filter(([, v]) => v).map(([k, v]) => [<dt key={k + "k"}>{k}</dt>, <dd key={k + "v"} title={v}>{v}</dd>])}
    </dl>
  );
}

function Page({ page, data, lane }: { page: RunPage; data: RunPayload; lane: Lane | null }) {
  const back = () => setMachinePage("");
  const onKey = (e: KeyboardEvent) => e.key === "Escape" && (e.stopPropagation(), back());
  const title = PAGES.find(([p]) => p === page)?.[1] || page;
  return (
    <div className="ri-page" data-testid="run-page" data-block={page} onKeyDown={onKey}>
      <header className="ri-page-head" data-density="bar">
        <Button size="sm" variant="ghost" onClick={back} data-testid="run-page-back" title="Back to the summary (Esc)">Back</Button>
        <b>{title}</b>
        <span className="mono muted">{lane ? `lane ${lane.lane}` : `run ${data.run.run_id}`}</span>
      </header>
      {page === "plan" ? <PlanPage data={data} lane={lane} /> : page === "claims" ? <ClaimsPage data={data} lane={lane} />
        : page === "diff" ? <DiffPage data={data} lane={lane} /> : page === "test" ? <TestPage data={data} lane={lane} /> : <LogPage lane={lane} />}
    </div>
  );
}

export function RunInspector({ kind, id }: { kind: "run" | "lane"; id: string }) {
  const data = useOrch((s) => s.data);
  const page = useMachinePage() as RunPage | "";
  const [run, n] = kind === "lane" ? [id.slice(0, id.lastIndexOf(":")), Number(id.slice(id.lastIndexOf(":") + 1))] : [id, 0];
  const lane = (data?.run.run_id === run && data.lanes.find((l) => l.lane === n)) || null;
  const workerKey = useWorkerKey(lane);
  const watch = useFleet((s) => (data?.live ? runSession(s, data.run.run_id, [data.run.lead_holder || "", ...data.lanes.map((l) => l.holder)]) : ""));
  if (!data || data.run.run_id !== run) return <p className="muted" data-testid="run-gone">Run {run} is not on Live any more: its report is in History.</p>;
  if (kind === "lane" && !lane) return <p className="muted" data-testid="run-gone">Lane {n} of run {run} is not in the run any more.</p>;
  if (page && PAGES.some(([p]) => p === page)) return <Page page={page as RunPage} data={data} lane={lane} />;
  const g = data.goal;
  const last = lane?.history.length ? lane.history[lane.history.length - 1].text : "";
  const counts = Object.entries(data.lanes.reduce<Record<string, number>>((m, l) => ((m[LANE_LABEL[l.state] || "pending"] = (m[LANE_LABEL[l.state] || "pending"] || 0) + 1), m), {}))
    .map(([s, c]) => `${c} ${s}`).join(", ");
  const rows: [string, string][] = lane
    ? [["GOAL", g.what], ["OWNS", ownsOf(lane, data.claims || []).join(", ") || "nothing yet"], ["STATE", [LANE_LABEL[lane.state] || lane.state || "pending", lane.error].filter(Boolean).join(": ")],
       ["LAST OUTPUT", short(last, 240) || "nothing yet"], ["COST", cost(lane.cost_usd)], ["MODEL", lane.model || g.worker || "the worker role's model"], ["WORKTREE", lane.branch]]
    : [["GOAL", g.what], ["DONE WHEN", g.done_when], ["STATE", data.run.state === "planned" ? "the plan waits on you" : data.run.state], ["LANES", counts || "none yet"],
       ["COST", cost(data.run.cost_usd)], ["THE GATE", g.test || "the lineup's test, if it names one"]];
  return (
    <div className="ri-sum rn-sum" data-testid="run-inspector" data-pick={kind} data-run={run} data-lane={lane?.lane || undefined}>
      <div className="rn-title">
        <b>{lane ? `lane ${lane.lane}: ${short(lane.title || lane.job, 60)}` : `goal run ${run}`}</b>
        {lane && <button className="og-link mono" onClick={() => pickLive("run", run)} data-testid="run-to-lead" title="The run's lead: the whole run">the run</button>}
      </div>
      <Facts rows={rows} />
      {!!lane?.opt_ins?.length && <p className="mono muted" data-testid="lane-optins">{lane.opt_ins.join(" · ")}</p>}
      <div className="rn-acts" data-density="bar">
        {data.live && <Stop run={run} />}
        {data.run.state === "planned" && <Button size="sm" variant="primary" onClick={reviewPlan} data-testid="run-review">Review the plan</Button>}
        {workerKey && <Button size="sm" variant="ghost" onClick={() => pickLive("agent", workerKey)} data-testid="run-steer" title="Its worker in this inspector: Steer, Pause, Stop, Take over">Steer its worker</Button>}
        {watch && <WatchInSession session={watch} testid="orchestra-watch-session" />}
      </div>
      <ul className="ri-rows" aria-label="Open one block">
        {PAGES.map(([p, label]) => (
          <li key={p} className="ri-row" data-density="row" data-block={p}>
            <button className="ri-row-main" onClick={() => setMachinePage(p)} data-testid={`run-block-${p}`}><span className="ri-row-title">{label}</span></button>
            <Button size="sm" variant="ghost" onClick={() => setMachinePage(p)} data-testid={`run-open-${p}`} aria-label={`Open ${label}`}>Open</Button>
          </li>
        ))}
      </ul>
      <button className="og-link mono" onClick={clearPick} data-testid="run-unpick">nothing picked</button>
    </div>
  );
}
