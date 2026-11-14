// The lit Map's overlay (3.6.0.0 R4, the v3 design's "While a session runs, the same map lights up"): ONE pure function
// from what one session says -- its agent rows (GET fleet / the feed's agent_state; in a replay, the rows at the
// scrubber's moment) and its map frames (crew/map_events.py: map_hop, map_step; in a replay, the same events from its
// log) -- to what the map draws over the boxes and lines he built: each box's state, what it does now and its cost;
// the hand-off moving along the line the runtime's receipt named; an opened workflow box's steps; the helpers the
// session made up, under the box that started them; and every row that matches nothing, shown in the strip (never
// dropped). Live and replay call the same function, so a replay lights the map as the run did. No runtime imports
// (tests/test_map_overlay.py runs it in node).
//
// Matching a row to a box: its `crew.box` (the runtime tagged the spawn: crew/map_run.py), else a workflow box whose
// workflow its `square` names (a step's agent, the workflow's node), else an agent box that has its name; a row none of
// those claim is a helper made up for the task, under the box its parent row belongs to; a row whose parent belongs to
// no box (or a tag naming a box the map no longer has) is a stranger: the strip shows it, tagged.

export type OvRow = {
  agent_id: string; parent?: string | null; name?: string | null; role?: string | null; state?: string | null; cost_usd?: number | null;
  current?: string | null; task?: string | null; model?: string | null; kind?: string | null;
  crew?: { map?: string; box?: string; line?: string; made_up?: boolean } | null; square?: { name?: string } | null;
};
export type OvEvent = { event: string; data: Record<string, unknown> };
export type OvMap = { boxes: { id: string; agent?: string | string[]; workflow?: string }[]; lines: { from: string; to: string }[] };
export type BoxState = "working" | "waiting" | "done" | "failed" | "idle";
export type OvBox = { state: BoxState; doing: string; cost: number; agents: string[]; models: string[] };
export type Pulse = { from: string; to: string; task: string; t: number; background: boolean };
export type LineLit = { t: number; task: string; why: string; background: boolean; running: boolean; skipped: string };
export type Helper = { aid: string; box: string; name: string; task: string; state: BoxState; cost: number; model: string };
export type Stranger = { aid: string; name: string; why: string; state: BoxState };
export type StepLit = { n: number; name: string; state: string; agents: string[]; rounds: number; checks: number; said: string };
export type Steps = { state: string; steps: StepLit[] };
export type Overlay = {
  boxes: Record<string, OvBox>; lines: Record<string, LineLit>; pulses: Pulse[]; helpers: Helper[]; strangers: Stranger[];
  steps: Record<string, Steps>; waiting: string[]; gone: string[];
  facts: { working: number; waiting: number; cost: number; models: string[]; hops: number };
};

export const PULSE_S = 4; // the line's label shows the task this long after a hand-off, then its When again
const LIVE = ["queued", "running", "paused"];
const num = (v: unknown): number => (typeof v === "number" && isFinite(v) ? v : 0);
const str = (v: unknown): string => (v == null ? "" : String(v));
export const lineKey = (from: string, to: string) => `${from}>${to}`;

export function stateOf(rows: OvRow[]): BoxState {
  const s = rows.map((r) => str(r.state));
  if (s.includes("waiting")) return "waiting";
  if (s.some((x) => LIVE.includes(x))) return "working";
  if (!s.length) return "idle";
  if (s.includes("failed") && !s.includes("done")) return "failed";
  return "done";
}

/** What a box does now, in a few words: its first live row's tool or "thinking", "waiting on you", "done". */
export function doingOf(rows: OvRow[], state: BoxState): string {
  if (state === "idle") return "not used yet";
  if (state === "waiting") return "waiting on you";
  if (state === "done" || state === "failed") return state === "done" ? "done" : "failed";
  const r = rows.find((x) => LIVE.includes(str(x.state)) && str(x.current)) || rows.find((x) => LIVE.includes(str(x.state)));
  const cur = str(r?.current).replace(/^([A-Za-z_]+):\s*/, "$1 ").trim();
  const words = cur && cur !== "thinking" ? cur : "thinking";
  return words.length > 44 ? words.slice(0, 41) + "..." : words;
}

function boxOf(m: OvMap): { byName: Map<string, string>; byFlow: Map<string, string>; ids: Set<string> } {
  const byName = new Map<string, string>(), byFlow = new Map<string, string>(), ids = new Set(["main", ...m.boxes.map((b) => b.id)]);
  for (const b of m.boxes) {
    if (b.workflow) byFlow.set(b.workflow, b.id);
    for (const a of Array.isArray(b.agent) ? b.agent : b.agent ? [b.agent] : []) if (!byName.has(a)) byName.set(a, b.id);
  }
  return { byName, byFlow, ids };
}

/** Each row's place: a box id (`box`), a helper under a box (`helper`), or nothing (`stranger`, with why). */
export function place(m: OvMap, rows: OvRow[]): Map<string, { box: string; helper: boolean; why: string }> {
  const { byName, byFlow, ids } = boxOf(m);
  const byId = new Map(rows.map((r) => [r.agent_id, r]));
  const out = new Map<string, { box: string; helper: boolean; why: string }>();
  const resolve = (r: OvRow, depth = 0): { box: string; helper: boolean; why: string } => {
    const got = out.get(r.agent_id);
    if (got) return got;
    let p: { box: string; helper: boolean; why: string };
    const tag = r.crew || null;
    if (r.agent_id === "main" || (!r.parent && str(r.kind) === "main")) p = { box: "main", helper: false, why: "" };
    else if (tag?.box) p = ids.has(tag.box) ? { box: tag.box, helper: !!tag.made_up, why: "" } : { box: "", helper: false, why: `its box ${tag.box} is not on this map (removed since)` };
    else if (r.square?.name && byFlow.has(str(r.square.name))) p = { box: byFlow.get(str(r.square.name))!, helper: false, why: "" };
    else if (byName.has(str(r.name))) p = { box: byName.get(str(r.name))!, helper: false, why: "" };
    else {
      const parent = r.parent ? byId.get(r.parent) : undefined;
      const up = parent && depth < 24 ? resolve(parent, depth + 1) : null;
      p = up && up.box ? { box: up.box, helper: true, why: "" } : { box: "", helper: false, why: parent ? "its parent is on no box" : "no box and no parent on this map" };
    }
    out.set(r.agent_id, p);
    return p;
  };
  for (const r of rows) resolve(r);
  return out;
}

function stepsOf(evs: OvEvent[]): Record<string, Steps> {
  const out: Record<string, Steps> = {};
  for (const { event, data: d } of evs) {
    if (event !== "map_step") continue;
    const box = str(d.box);
    const w = (out[box] = out[box] || { state: "running", steps: [] });
    const n = num(d.n);
    const at = (i: number): StepLit => {
      let s = w.steps.find((x) => x.n === i);
      if (!s) w.steps.push((s = { n: i, name: `step ${i}`, state: "waiting", agents: [], rounds: 0, checks: 0, said: "" }));
      return s;
    };
    if (d.kind === "start") {
      w.state = "running";
      w.steps = (Array.isArray(d.steps) ? d.steps : []).map((s: unknown, i: number) => ({
        n: i + 1, name: str((s as { name?: unknown })?.name ?? s), state: "waiting", agents: [], rounds: 0, checks: 0, said: "" }));
    } else if (d.kind === "step") Object.assign(at(n), { name: str(d.name) || at(n).name, state: str(d.state) || at(n).state, rounds: num(d.rounds) || at(n).rounds });
    else if (d.kind === "agent") {
      const s = at(n);
      if (d.name && !s.agents.includes(str(d.name))) s.agents.push(str(d.name));
      if (s.state === "waiting") s.state = "running";
      s.rounds = Math.max(s.rounds, num(d.round));
      if (d.said) s.said = str(d.said);
    } else if (d.kind === "check") at(n).checks += 1;
    else if (d.kind === "end") w.state = str(d.state) || "done";
  }
  return out;
}

/** The overlay of one session on the map `m`, at `now` (epoch seconds). */
export function overlay(m: OvMap, rows: OvRow[], events: OvEvent[], now: number): Overlay {
  const where = place(m, rows);
  const groups = new Map<string, OvRow[]>();
  const helpers: Helper[] = [], strangers: Stranger[] = [];
  for (const r of rows) {
    const p = where.get(r.agent_id)!;
    const st = stateOf([r]);
    if (!p.box) strangers.push({ aid: r.agent_id, name: str(r.name || r.role || r.agent_id), why: p.why, state: st });
    else if (p.helper) helpers.push({ aid: r.agent_id, box: p.box, name: str(r.name || r.agent_id), task: str(r.task), state: st, cost: num(r.cost_usd), model: str(r.model) });
    else groups.set(p.box, [...(groups.get(p.box) || []), r]);
  }
  const boxes: Record<string, OvBox> = {};
  for (const id of ["main", ...m.boxes.map((b) => b.id)]) {
    const rs = groups.get(id) || [];
    const own = id === "main" ? rs.filter((r) => r.agent_id === "main") : rs;
    const state = id === "main" ? (stateOf(own) === "idle" ? "working" : stateOf(own)) : stateOf(rs);
    boxes[id] = { state, doing: doingOf(own, state), cost: rs.reduce((a, r) => a + num(r.cost_usd), 0), agents: rs.map((r) => r.agent_id),
                  models: [...new Set(rs.map((r) => str(r.model)).filter(Boolean))] };
  }
  const lines: Record<string, LineLit> = {};
  const pulses: Pulse[] = [], gone = new Set<string>();
  const on = new Set(m.lines.map((l) => lineKey(l.from, l.to)));
  let hops = 0;
  for (const { event, data: d } of events) {
    if (event !== "map_hop") continue;
    const from = str(d.from), to = str(d.to), k = lineKey(from, to), t = num(d.t);
    if (!on.has(k)) {
      gone.add(to);
      continue;
    }
    const was = lines[k] || { t: 0, task: "", why: "", background: false, running: false, skipped: "" };
    if (d.state === "skipped") lines[k] = { ...was, skipped: str(d.why) };
    else if (d.state === "start") {
      hops += 1;
      lines[k] = { t, task: str(d.task), why: str(d.why), background: !!d.background, running: true, skipped: "" };
      if (now - t <= PULSE_S && now >= t) pulses.push({ from, to, task: str(d.task), t, background: !!d.background });
    } else if (d.state === "end") lines[k] = { ...was, running: false };
  }
  const all = Object.values(boxes);
  return {
    boxes, lines, pulses, helpers, strangers, steps: stepsOf(events),
    waiting: Object.entries(boxes).filter(([, b]) => b.state === "waiting").map(([id]) => id).concat(helpers.filter((h) => h.state === "waiting").map((h) => h.box)),
    gone: [...gone].filter((id) => !m.boxes.some((b) => b.id === id)),
    facts: { working: all.filter((b) => b.state === "working").length + helpers.filter((h) => h.state === "working").length,
             waiting: all.filter((b) => b.state === "waiting").length + helpers.filter((h) => h.state === "waiting").length,
             cost: rows.reduce((a, r) => a + num(r.cost_usd), 0), models: [...new Set(rows.map((r) => str(r.model)).filter(Boolean))], hops },
  };
}

/** Recorded events up to `t` (a replay at the scrubber's moment). */
export const eventsAt = (evs: OvEvent[], t: number): OvEvent[] => evs.filter((e) => num(e.data.t) <= t + 1e-6);
