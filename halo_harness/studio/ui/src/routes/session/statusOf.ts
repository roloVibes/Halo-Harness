// What Session's status line is told (3.6.0.2 R23), from the chosen session's agent rows (GET live / the feed) and its
// map frames (map_step's start names a workflow's steps): who works = the rows at work now, never a row that only waits
// on agents it started (an Agent / Task / Workflow call: "delegating" goes); on what = that row's tool in a few words, or
// "the workflow {W}, step {i} of {n}"; waiting for you (a row waits) or a model reply (the worker is thinking); the
// session's cost. The sentence itself is truth.ts's statusLine. Pure: `import type` only (node-tested).
import type { AgentRow } from "../fleet/types";
import type { OvEvent } from "../crew/map/overlay";
import type { Status } from "../crew/map/truth";

const LIVE = ["queued", "running", "paused"];
const FINISHED = ["done", "failed", "stopped"];
const WAITS_ON_AGENTS = /^(Agent|Task|Workflow)\b/; // routes/crew/live/narrate.ts: the calls that hand work to other agents

const str = (v: unknown): string => (v == null ? "" : String(v));

/** A workflow's step count: its last map_step start frame's `steps`, else the highest step its rows name. */
function stepsIn(name: string, rows: AgentRow[], events: OvEvent[]): number {
  const start = [...events].reverse().find((e) => e.event === "map_step" && e.data.kind === "start" && str(e.data.workflow) === name);
  const n = Array.isArray(start?.data.steps) ? (start!.data.steps as unknown[]).length : 0;
  return n || Math.max(0, ...rows.filter((r) => r.crew?.workflow === name).map((r) => Number(r.crew?.step) || 0));
}

/** R23: the status line's facts; `off` = the hand-offs outside the map (batch 4 feeds it). */
export function statusOf(rows: AgentRow[], events: OvEvent[], busy: boolean, off = 0): Status {
  const cost = rows.reduce((a, r) => a + (Number(r.cost_usd) || 0), 0);
  const live = rows.filter((r) => LIVE.includes(str(r.state)));
  // at work = running now (a queued or paused row is not yet / not now), never only waiting on agents it started
  const work = live.filter((r) => str(r.state) === "running" && !WAITS_ON_AGENTS.test(str(r.current)));
  const asks = rows.some((r) => str(r.state) === "waiting");
  if (!live.length && !asks && !busy) {
    const done = rows.some((r) => FINISHED.includes(str(r.state)));
    return { state: done ? "done" : "idle", rows: [], what: "", workflow: null, waiting: null, cost, off };
  }
  const name = (r: AgentRow) => (!r.parent || r.agent_id === "main" ? "main" : str(r.name || r.role || r.agent_id));
  const first = work[0];
  const cur = str(first?.current).replace(/^([A-Za-z_]+):\s*/, "$1 ").trim();
  const flow = first?.crew?.workflow ? str(first.crew.workflow) : "";
  return {
    state: "working",
    rows: work.map((r) => ({ name: name(r), state: "working" })),
    what: cur === "thinking" ? "" : cur,
    workflow: flow ? { name: flow, step: Number(first!.crew!.step) || 1, of: stepsIn(flow, rows, events) } : null,
    waiting: asks ? "you" : first && (!cur || cur === "thinking") ? "model" : null,
    cost, off,
  };
}
