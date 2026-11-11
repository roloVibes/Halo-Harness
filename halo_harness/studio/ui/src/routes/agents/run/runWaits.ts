// What a goal run's boxes wait on (3.4.0.0 D "the runs fold"; waits.ts's words for the session's agents): the gate and
// the merge are steps on the waiting path. Pure, from the run's payload:
//
//   lead  planned: you (review the plan); the split running: a model reply (the lead's split); lanes at work: an agent
//         (the lane the run waits on: one the gate sent back first, else one writing, else the newest); the merge
//         running: a tool, "the merge"; the test or the gate running: a tool, "the gate: <test>"
//   lane  joined: nothing (queued); writing: nothing (writing); written: a tool, "the merge"; in review: a tool, "the
//         gate"; waiting: an agent, the lane it runs after (else "a claim")
//
// `who` of an agent wait is the lane node's id (Live follows it down the waiting path; a lane has no session key).
import type { RunPayload } from "../../orchestra/types";
import type { LiveNode } from "../../roles/liveModel";
import type { Wait } from "../live/waits";

const ms = (s: number | null | undefined) => (s ? s * 1000 : null);

export function runWaitOf(n: LiveNode, data: RunPayload | null): Wait | null {
  if (!data?.live || !n.run || n.run !== data.run.run_id) return null;
  const lead = `run:${n.run}`;
  if (!n.lane) {
    if (data.run.state === "planned") return { kind: "you", what: `run ${n.run}: review the plan`, since: ms(data.run.created), who: n.id };
    const step = (data.workflow?.steps || []).find((s) => s.state === "running" && s.kind !== "worker");
    const test = `the gate: ${data.goal.test || "its test"}`;
    if (step?.kind === "merge") return { kind: "tool", what: "the merge", since: null, who: n.id };
    if (step?.kind === "test" || step?.kind === "gate") return { kind: "tool", what: test, since: null, who: n.id };
    const at = data.lanes.filter((l) => !["merged", "failed", ""].includes(l.state));
    const pick = at.find((l) => l.state === "waiting") || at.find((l) => l.state === "writing") || at[at.length - 1];
    if (pick) return { kind: "agent", what: `lane ${pick.lane}`, since: ms(pick.started), who: `${lead}:lane:${pick.lane}` };
    if (step?.kind === "split" || !data.lanes.length) return { kind: "model", what: "the lead's split", since: ms(data.run.created), who: n.id };
    return { kind: "tool", what: test, since: null, who: n.id };
  }
  const l = data.lanes.find((x) => x.lane === n.lane);
  if (!l) return null;
  if (l.state === "joined" || !l.state) return { kind: "nothing", what: "queued, not started", since: null, who: n.id };
  if (l.state === "writing") return { kind: "nothing", what: "working: writing", since: null, who: n.id };
  if (l.state === "written") return { kind: "tool", what: "the merge", since: null, who: n.id };
  if (l.state === "in_review") return { kind: "tool", what: `the gate: ${data.goal.test || "its test"}`, since: null, who: n.id };
  if (l.state === "waiting") {
    const up = data.lanes.find((x) => (l.after || []).includes(x.job) && x.state !== "merged");
    return up ? { kind: "agent", what: `lane ${up.lane}`, since: null, who: `${lead}:lane:${up.lane}` } : { kind: "tool", what: "a claim", since: null, who: n.id };
  }
  return null;
}
