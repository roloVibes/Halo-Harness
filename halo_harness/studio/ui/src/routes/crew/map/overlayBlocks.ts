// A running saved workflow, drawn as itself (3.6.0.2 R14): one block per workflow W the session runs, every step a row
// "{i} {step} · {agent} · {model} · done | working | next | failed". Built from the step runner's `map_step` frames (keyed
// `box || "workflow:" + W`, crew/map_events.py step_emit; the `start` frame names every step) and from the rows the
// runtime tagged `crew.workflow = W, step = i` (R13): a step's agent and model are its row's once it runs, before that the
// step list's. A step's state is the further of its row's and its frames' (next < working < done | failed), so frames
// light the rows in order and a row never steps back. Pure: `import type` only (node runs it through overlay.ts).
import type { StepRow } from "./mapTypes";
import type { OvEvent, OvMap, OvRow } from "./overlay";

export type BlockLit = {
  box: string | null; // the map box whose workflow is W, else none: the block is drawn under its caller
  caller: string; // the box that called it (the hop to `workflow:{W}`, else its rows' parent's box, else main)
  state: string; // running | done | failed
  steps: StepRow[];
  off: boolean | null; // the verdict of the hop that started it (null: no hop seen)
};
type St = StepRow["state"];

export const str = (v: unknown): string => (v == null ? "" : String(v)); // overlay.ts's too
const RANK: Record<St, number> = { next: 0, working: 1, done: 2, failed: 2 };
const further = (a: St, b: St): St => (RANK[b] > RANK[a] ? b : a);

/** A row's state as a step's word. */
export function rowStep(state: string): St {
  if (["running", "paused", "waiting"].includes(state)) return "working";
  if (state === "done") return "done";
  if (["failed", "error", "stopped", "cancelled"].includes(state)) return "failed";
  return "next";
}
/** A frame's step state as a step's word. */
function frameStep(state: string): St {
  if (state === "running") return "working";
  if (state === "done" || state === "skipped") return "done";
  if (["failed", "capped", "stopped"].includes(state)) return "failed";
  return "next";
}

/** The blocks of the workflows the session runs: `boxOf(aid)` = the box an agent row is placed in. */
export function blocksOf(m: OvMap, rows: OvRow[], events: OvEvent[], boxOf: (aid: string) => string): Record<string, BlockLit> {
  const byFlow = new Map(m.boxes.filter((b) => b.workflow).map((b) => [b.workflow!, b.id]));
  const flowOfBox = new Map(m.boxes.filter((b) => b.workflow).map((b) => [b.id, b.workflow!]));
  const out: Record<string, BlockLit> = {};
  const get = (w: string): BlockLit => (out[w] = out[w] || { box: byFlow.get(w) || null, caller: "", state: "running", steps: [], off: null });
  const at = (b: BlockLit, i: number): StepRow => {
    let s = b.steps.find((x) => x.n === i);
    if (!s) b.steps.push((s = { n: i, step: `step ${i}`, agent: "", model: "", state: "next" }));
    return s;
  };
  for (const { event, data: d } of events) {
    const box = str(d.box), to = str(d.to);
    if (event === "map_hop" && to.startsWith("workflow:") && d.state === "start") {
      const b = get(to.slice(9));
      b.caller = str(d.from) || b.caller;
      b.off = !!d.off;
      continue;
    }
    if (event !== "map_step") continue;
    const w = str(d.workflow) || (box.startsWith("workflow:") ? box.slice(9) : flowOfBox.get(box) || "");
    if (!w) continue;
    const b = get(w);
    if (d.kind === "start") {
      b.state = "running";
      b.steps = (Array.isArray(d.steps) ? d.steps : []).map((s: unknown, i: number) => {
        const o = (s && typeof s === "object" ? s : { name: s }) as { name?: unknown; agent?: unknown; agents?: unknown };
        const agent = str(o.agent) || (Array.isArray(o.agents) ? o.agents.map(str).join(" + ") : "");
        return { n: i + 1, step: str(o.name), agent, model: "", state: "next" as St };
      });
    } else if (d.kind === "step") {
      const s = at(b, Number(d.n) || 0);
      if (d.name) s.step = str(d.name);
      s.state = further(s.state, frameStep(str(d.state)));
    } else if (d.kind === "agent") {
      const s = at(b, Number(d.n) || 0);
      if (d.name && !s.agent) s.agent = str(d.name);
      s.state = further(s.state, "working");
    } else if (d.kind === "end") b.state = str(d.state) || "done";
  }
  for (const r of rows) {
    const w = str(r.crew?.workflow);
    if (!w) continue;
    const b = get(w);
    const s = at(b, Number(r.crew?.step) || 0);
    s.agent = str(r.crew?.agent) || str(r.name) || s.agent;
    s.model = str(r.model) || s.model;
    s.state = further(s.state, rowStep(str(r.state)));
    if (!b.caller && r.parent) b.caller = boxOf(str(r.parent));
  }
  for (const b of Object.values(out)) {
    b.steps.sort((p, q) => p.n - q.n);
    b.caller = b.caller || "main";
    if (b.state === "running" && b.steps.length && b.steps.every((s) => s.state === "done")) b.state = "done";
  }
  return out;
}

/** The step a running block is on (its first working step), for its head "workflow {W} · step {i} of {n}". */
export const runningStep = (b: { state: string; steps: StepRow[] }): number | undefined =>
  b.state === "running" ? b.steps.find((s) => s.state === "working")?.n : undefined;
