// Agents -> Live draws a live Orchestra run on the same tree (3.3.16.0 R1, the ROADMAP's Agents entry): the run's lead
// as a node, each lane a node under it with its number in the lane's colour and its worktree badge (the lane's
// branch), its state and its title. The run is the one Runs has open (routes/orchestra/store.ts: the newest at load)
// and only while it is live; its nodes join the session's agents (routes/roles/LiveMap.tsx) and are laid out with
// them. A lane node is not a session agent: a click opens Runs focused on that lane.
import { short } from "../../orchestra/format";
import { focusLane, LANE_LABEL, laneColor } from "../../orchestra/store";
import type { RunPayload } from "../../orchestra/types";
import type { LiveBox } from "../../roles/liveLayout";
import type { LiveNode } from "../../roles/liveModel";
import { setAgentsView } from "../store";

const STATE: Record<string, string> = { writing: "running", in_review: "running", written: "running", joined: "queued", waiting: "waiting", merged: "done", failed: "failed" };
const GLOW: Record<string, LiveNode["glow"]> = { running: "working", waiting: "waiting", done: "done", failed: "failed" };

const blank = { key: "", model: "", pick: "", activity: "", card: "", cardLabel: "", current: "", cost: null, started: null, ended: null } as const;

/** The live run's lead and its lanes as Live nodes ([] when no run is live). */
export function runNodes(data: RunPayload | null): LiveNode[] {
  if (!data?.live) return [];
  const run = data.run.run_id;
  const lead = `run:${run}`;
  const out: LiveNode[] = [{ ...blank, id: lead, parent: null, name: "lead", role: "orchestra", model: data.goal.lead || "", state: "running", glow: "working",
                             task: data.goal.what, current: `run ${run}`, cost: data.run.cost_usd, run, started: data.run.created }];
  for (const l of data.lanes) {
    const state = STATE[l.state] || "queued";
    out.push({ ...blank, id: `${lead}:lane:${l.lane}`, parent: lead, name: `lane ${l.lane}`, role: "lane", model: data.goal.worker || "", state,
               glow: GLOW[state] || "", task: l.title || l.claims.join(", "), current: LANE_LABEL[l.state] || l.state || "joining",
               cost: l.cost_usd, started: l.started, ended: l.ended, run, lane: l.lane, worktree: l.branch || "" });
  }
  return out;
}

/** A run's node on the Live tree: the lead, or a lane with its number and worktree. */
export function RunNodeCard({ b }: { b: LiveBox }) {
  const n = b.node;
  const style = { left: b.x, top: b.y, width: b.w, height: b.h };
  const open = () => (setAgentsView("runs"), n.lane && focusLane(n.lane));
  if (!n.lane)
    return (
      <div className="rlm-node ag-live-lead" style={style} role="button" tabIndex={0} onClick={open} data-testid="agents-live-lead" data-run={n.run}
           data-glow={n.glow || undefined} title={`Orchestra run ${n.run}: ${n.task} (a click opens it in Runs)`}>
        <div className="rlm-head"><span className="rlm-dot" aria-hidden="true" /><b className="rlm-name">lead</b><span className="og-chip mono rlm-role">run</span></div>
        <div className="mono muted rlm-line">{n.run}</div>
        <div className="muted rlm-line">{short(n.task, 60)}</div>
      </div>
    );
  return (
    <div className="rlm-node ag-live-lane" style={style} role="button" tabIndex={0} onClick={open} data-testid="agents-live-lane" data-lane={n.lane}
         data-lc={laneColor(n.lane)} data-state={n.state} data-glow={n.glow || undefined} data-worktree={n.worktree || undefined}
         title={`lane ${n.lane} of run ${n.run}: ${n.task} (a click opens it in Runs)`}>
      <div className="rlm-head">
        <span className="og-lane-n mono">{n.lane}</span>
        <b className="rlm-name">{short(n.task || n.name, 22)}</b>
        <span className="spacer" />
        <span className="og-badge mono">{n.current}</span>
      </div>
      <div className="mono muted rlm-line ag-worktree" data-testid="agents-live-worktree" title={n.worktree}>{n.worktree ? `⎇ ${short(n.worktree, 34)}` : "worktree: not yet"}</div>
      <div className="mono muted rlm-line">{n.model ? short(n.model.replace(/^[a-z]+:/, ""), 30) : "the worker role's model"}</div>
    </div>
  );
}
