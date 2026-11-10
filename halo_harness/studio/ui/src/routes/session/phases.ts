// The Live timeline's phases (3.3.16.2, "the timeline shows the mix"): each agent's lane drawn in segments by what it
// did, read off the Live column's rows -- thinking (a THINK row, from its first piece to its last), running a tool
// (a tool row until its result), writing (its text, its hand-back, its words to another agent), waiting on you (an
// ask, until its next row) -- and idle between them. Fleet/Timeline.tsx draws them (`phases`); a thinking segment
// carries its row's `n`, so a click scrolls the column to that thought.
import type { AgentKey } from "../fleet/types";
import type { LiveLine } from "../shared/liveFeed";

export type Phase = "thinking" | "tool" | "writing" | "waiting" | "idle";
export type PhaseSeg = { t0: number; t1: number; phase: Phase; n?: number };

export const PHASE_WORD: Record<Phase, string> = { thinking: "thinking", tool: "running a tool", writing: "writing", waiting: "waiting on you", idle: "idle" };
const WRITE_MIN = 400; // ms: a text that came in one piece still shows

const phaseOf = (l: LiveLine): Phase | null =>
  l.kind === "thinking" ? "thinking" : l.kind === "tool" ? "tool" : l.kind === "ask" ? "waiting"
    : l.kind === "text" || l.kind === "output" || l.kind === "talk" ? "writing" : null;

/** Every agent's segments, in time order, idle filled in between (an open segment ends at Infinity: now). */
export function phaseMap(lines: LiveLine[]): Map<AgentKey, PhaseSeg[]> {
  const raw = new Map<AgentKey, PhaseSeg[]>();
  const lastAsk = new Map<AgentKey, PhaseSeg>();
  for (const l of lines) {
    const ask = lastAsk.get(l.key);
    if (ask && ask.t1 === Infinity) ask.t1 = l.t0; // an ask waits until the agent's next row
    const phase = phaseOf(l);
    if (!phase) continue;
    const open = (l.kind === "tool" && !l.ended) || (l.kind === "thinking" && !l.done) || phase === "waiting";
    const t1 = open ? Infinity : Math.max(l.ended || l.t0, l.t0 + (phase === "writing" ? WRITE_MIN : 200));
    const seg: PhaseSeg = { t0: l.t0, t1, phase, ...(phase === "thinking" ? { n: l.n } : {}) };
    if (phase === "waiting") lastAsk.set(l.key, seg);
    const list = raw.get(l.key) || [];
    list.push(seg);
    raw.set(l.key, list);
  }
  const out = new Map<AgentKey, PhaseSeg[]>();
  for (const [key, list] of raw) {
    list.sort((a, b) => a.t0 - b.t0);
    const full: PhaseSeg[] = [];
    for (let i = 0; i < list.length; i++) {
      const s = list[i];
      const next = list[i + 1];
      const end = next ? Math.min(s.t1, next.t0) : s.t1;
      if (end > s.t0) full.push({ ...s, t1: end });
      if (next && end < next.t0) full.push({ t0: end, t1: next.t0, phase: "idle" });
      if (!next && end !== Infinity) full.push({ t0: end, t1: Infinity, phase: "idle" });
    }
    out.set(key, full);
  }
  return out;
}

/** "12 s", "1 min 4 s", "800 ms": a segment's length. */
export function spanWords(ms: number): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))} ms`;
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}
