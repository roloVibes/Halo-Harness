// A goal run on Agents -> Live (3.3.16.0 R1; 3.4.0.0 D "the runs fold": a goal run is a job on Live like any other).
// While it runs -- or waits on you for its plan -- its lead is a node and its lanes are agents in the run's block under
// it (a group box, groups.ts kind `run`: the goal, its lanes, its cost, its time). Each box says one fact per row, the
// box grown to hold them (never squished; CSS ellipsis + the row's tooltip): a lane's state, its model, its cost, what
// it owns (its claims) and its worktree; the lead's goal, its state, its lanes and the gate's test, and "Review the
// plan" while the plan waits on you. A click puts it in Live's inspector (routes/agents/run/RunInspector.tsx: summary
// first, then one block per page); hover is its summary card. Nothing finished is drawn: an ended run is History's.
import type { KeyboardEvent } from "react";
import { short } from "../../orchestra/format";
import { LANE_LABEL, laneColor } from "../../orchestra/store";
import type { RunPayload } from "../../orchestra/types";
import type { LiveBox } from "../../roles/liveLayout";
import type { LiveNode } from "../../roles/liveModel";
import { useHover } from "../../../lib/hover/useHover";
import { LaneHover } from "../hover/lane"; // 3.3.16.1: the lead's and a lane's hover cards
import { ownsOf } from "../run/Owns";
import { reviewPlan } from "../run/planPanel";
import { pickLive, useLivePick } from "./scope";
import { WaitsRow } from "./WaitsRow";
import type { GroupTag } from "./groups";

const STATE: Record<string, string> = { writing: "running", in_review: "running", written: "running", joined: "queued", waiting: "waiting", merged: "done", failed: "failed" };
const GLOW: Record<string, LiveNode["glow"]> = { running: "working", waiting: "waiting", done: "done", failed: "failed" };
const blank = { key: "", model: "", pick: "", activity: "", card: "", cardLabel: "", current: "", cost: null, started: null, ended: null } as const;
const bare = (m: string) => m.replace(/^[a-z]+:/, "");

/** The live run's lead and its lanes as Live nodes, the lanes in the run's block ([] when no run is live). */
export function runNodes(data: RunPayload | null): LiveNode[] {
  if (!data?.live) return [];
  const run = data.run.run_id;
  const lead = `run:${run}`;
  const planned = data.run.state === "planned";
  const block: GroupTag = { id: lead + ":block", kind: "run", parent: lead, title: short(data.goal.what, 60) || `run ${run}`,
                            why: `run ${run} · ${data.lanes.length} lane${data.lanes.length === 1 ? "" : "s"} · the gate: ${data.goal.test || "the lineup's test"}` };
  const out: LiveNode[] = [{ ...blank, id: lead, parent: null, name: "lead", role: "orchestra", model: data.goal.lead || "", state: planned ? "waiting" : "running",
                             glow: planned ? "waiting" : "working", task: data.goal.what, current: planned ? "the plan waits on you" : `run ${run}`,
                             cost: data.run.cost_usd, run, started: data.run.created }];
  for (const l of data.lanes) {
    const state = STATE[l.state] || "queued";
    out.push({ ...blank, id: `${lead}:lane:${l.lane}`, parent: lead, name: `lane ${l.lane}`, role: "lane", model: l.model || data.goal.worker || "", state,
               glow: GLOW[state] || "", task: l.title || l.claims.join(", "), current: LANE_LABEL[l.state] || l.state || "joining",
               cost: l.cost_usd, started: l.started, ended: l.ended, run, lane: l.lane, worktree: l.branch || "", group: block,
               owns: ownsOf(l, data.claims || []) });
  }
  return out;
}

const money = (v: number | null | undefined) => (v ? `$${v >= 1 ? v.toFixed(2) : v.toFixed(4)}` : "$0");
/** 3.4.1.1 (60): a replay's box before its cost is in the record says so, never $0. */
const costOf = (n: LiveNode) => (n.costUnknown ? "unknown at this moment" : money(n.cost));

function Row({ k, v, testid }: { k: string; v: string; testid?: string }) {
  return (
    <div className="mono rlm-line ag-run-row" data-testid={testid} title={`${k.toLowerCase()}: ${v}`}>
      <span className="ag-run-k">{k}</span>
      <span className="ag-run-v">{v}</span>
    </div>
  );
}

/** A run's node on the Live tree: the lead, or a lane with its number, a row per fact. */
export function RunNodeCard({ b }: { b: LiveBox }) {
  const n = b.node;
  const run = n.run || "";
  const pick = useLivePick();
  const style = { left: b.x, top: b.y, width: b.w, height: b.h };
  const open = () => (n.lane ? pickLive("lane", `${run}:${n.lane}`) : pickLive("run", run));
  const onKey = (e: KeyboardEvent) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open());
  const hv = useHover("lane", n.id, () => <LaneHover run={run} lane={n.lane} />);
  const t = hv.titles;
  const on = n.lane ? pick.kind === "lane" && pick.id === `${run}:${n.lane}` : pick.kind === "run" && pick.id === run;
  if (!n.lane)
    return (
      <div className="rlm-node ag-live-lead" style={style} role="button" tabIndex={0} onClick={open} onKeyDown={onKey} data-testid="agents-live-lead" data-run={run}
           data-state={n.state} data-glow={n.glow || undefined} data-on={on || undefined} title={t ? `Goal run ${run}: ${n.task} (a click: its summary in the inspector)` : undefined} {...hv.props}>
        <div className="rlm-head"><span className="rlm-dot" aria-hidden="true" /><b className="rlm-name">lead</b><span className="og-chip mono rlm-role">goal run</span></div>
        <Row k="GOAL" v={n.task} />
        <Row k="STATE" v={n.state === "waiting" ? "the plan waits on you" : n.state === "running" ? `running · ${n.current}` : n.state} testid="agents-live-lead-state" />
        <Row k="MODEL" v={n.model ? bare(n.model) : "the lead role's model"} />
        <Row k="COST" v={costOf(n)} />
        {n.state === "waiting" && (
          <button type="button" className="og-link mono ag-run-review" data-testid="agents-live-review" title="Open the plan review beside the canvas: edit the lanes, then Approve and run (or Reject)"
                  onClick={(e) => (e.stopPropagation(), reviewPlan())}>Review the plan</button>
        )}
        <WaitsRow id={n.id} />
      </div>
    );
  return (
    <div className="rlm-node ag-live-lane" style={style} role="button" tabIndex={0} onClick={open} onKeyDown={onKey} data-testid="agents-live-lane" data-lane={n.lane}
         data-lc={laneColor(n.lane)} data-state={n.state} data-glow={n.glow || undefined} data-worktree={n.worktree || undefined} data-on={on || undefined}
         title={t ? `lane ${n.lane} of run ${run}: ${n.task} (a click: its summary in the inspector)` : undefined} {...hv.props}>
      <div className="rlm-head">
        <span className="og-lane-n mono">{n.lane}</span>
        <b className="rlm-name" title={n.task}>{short(n.task || n.name, 40)}</b>
      </div>
      <Row k="STATE" v={n.current || n.state} testid="agents-live-lane-state" />
      <Row k="MODEL" v={n.model ? bare(n.model) : "the worker role's model"} />
      <Row k="COST" v={costOf(n)} />
      <Row k="OWNS" v={(n.owns || []).join(", ") || "nothing yet"} testid="lane-owns" />
      <div className="mono muted rlm-line ag-worktree" data-testid="agents-live-worktree" title={n.worktree || "no worktree yet"}>{n.worktree ? `⎇ ${n.worktree}` : "worktree: not yet"}</div>
      <WaitsRow id={n.id} />
    </div>
  );
}
