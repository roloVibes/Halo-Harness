// The true lines (3.6.0.5 package t, C12 C15 C22): after a build on Auto, what is ready in this session now and what is
// saved for the next session, as `builder_done` carries it (`ready`, `later`, `p3`, computed by crew/ready_now.py). The
// words are crew/ready_now.py's, letter for letter (tests/test_ready_lines.py pins each constant to its Python twin), and
// the head over Session's Live drawing (H1 H2 H3) comes from the same answer, so Studio and the terminal never disagree.
// 3.6.0.15 U4: an agent the card wrote and the session took is ready now (`ready_agents`, P1_AGENT); one it refused waits
// with the put's why (TOOL, MODE, BUILTIN).
// Pure: no React, no store, no DOM. built.ts imports this file; this file imports nothing of built.ts.
import { justBuilt, type Line } from "../crew/map/truth";

export type Later = { kind: "workflow" | "agent"; name: string; why: "WF" | "AG1" | "AG2" | "TOOL" | "MODE" | "BUILTIN";
  tool?: string; step?: string };
export type Ready = { ready: string[]; ready_agents: string[]; later: Later[]; p3: string[] };

export const FIRST_WORDS = ["Ready in this session now:", "Saved for your next session:", "Not run under its name:"] as const;
export const P1 = `${FIRST_WORDS[0]} {items}.`;
export const P1_ITEM = "the workflow {W}";
export const P1_AGENT = "the agent {x} (subagent_type `{x}`)";
export const P2 = `${FIRST_WORDS[1]} the {kind} {name} ({why}{step}).`;
export const P3 = `${FIRST_WORDS[2]} the workflow {W} (this project has its own workflow {W}, which runs first).`;
export const WHY = {
  WF: "this session started with no workflow, so it has no Workflow tool",
  AG1: "this session's list of agents was fixed when it started",
  AG2: "this session keeps the {name} it started with",
  TOOL: "it asks for {tool}, which this session's main does not have",
  MODE: "it asks for a mode above this session's",
  BUILTIN: "a built-in has that name",
} as const;
export const STEP = "; as a step of the workflow {W} it can run now";

/** `{key}` in `s` filled from `o`, in one pass (a filled value is never read again). */
const fill = (s: string, o: Record<string, string>): string => s.replace(/\{(\w+)\}/g, (all, k: string) => (k in o ? o[k] : all));

const isWhy = (w: unknown): w is Later["why"] => typeof w === "string" && w in WHY;

/** The answer a `builder_done` frame carries, or null when it carries none (an older session process sends no `ready`). */
export function readyOf(d: Record<string, unknown>): Ready | null {
  if (!Array.isArray(d.ready)) return null;
  const words = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
  const later: Later[] = [];
  for (const x of Array.isArray(d.later) ? d.later : []) {
    if (!x || typeof x !== "object") continue;
    const o = x as Record<string, unknown>;
    if ((o.kind !== "workflow" && o.kind !== "agent") || typeof o.name !== "string" || !isWhy(o.why)) continue;
    later.push({ kind: o.kind, name: o.name, why: o.why, ...(typeof o.tool === "string" ? { tool: o.tool } : {}),
      ...(typeof o.step === "string" && o.step ? { step: o.step } : {}) });
  }
  return { ready: words(d.ready), ready_agents: words(d.ready_agents), later, p3: words(d.p3) };
}

/** The lines for one answer: P1 once (the ready workflows, then the ready agents), one P2 per item that waits, one P3
 * per shadowed workflow. */
export function pLines(r: Ready): string[] {
  const out: string[] = [];
  const items = [...r.ready.map((w) => fill(P1_ITEM, { W: w })), ...(r.ready_agents || []).map((x) => fill(P1_AGENT, { x }))];
  if (items.length) out.push(fill(P1, { items: items.join(", ") }));
  for (const it of r.later) {
    const why = fill(WHY[it.why], { name: it.name, tool: it.tool || "" });
    out.push(fill(P2, { kind: it.kind, name: it.name, why, step: it.step ? fill(STEP, { W: it.step }) : "" }));
  }
  for (const w of r.p3) out.push(fill(P3, { W: w }));
  return out;
}

const open = (text: string): Line => ({ text, act: "open-workflows", label: "Open in Workflows" });

/** H1 H2 H3: the head on Auto for the workflow `w` the build wrote, from the same answer as the lines; else null. */
export function autoHead(w: string, r: Ready): Line | null {
  if (r.ready.includes(w)) return open(`Just built: the workflow ${w}. Ready in this session now, by name.`);
  if (r.p3.includes(w)) return open(`Just built: the workflow ${w}. This project has its own workflow ${w}, which runs under that name.`);
  if (r.later.some((x) => x.kind === "workflow" && x.name === w)) return open(`Just built: the workflow ${w}. It waits for your next session: ${WHY.WF}.`);
  return null;
}

/** What built.ts keeps of one build (its `Built` fits this). */
export type BuiltLike = { t: number; kind: "workflow" | "running" | "other" | null; map: string; workflow: string; next: string;
  ready: Ready | null };

/** The head and the lines over Session's Live drawing. Off Auto (a map of his, one model for everything): the head of
 * 3.6.0.2, no line. On Auto: a workflow on no map gets H1/H2/H3 (none when the frame carried no answer); a change to the
 * running map or another map keeps its head; the lines sit under the head, or alone for a build of agents only. */
export function builtView(b: BuiltLike, auto: boolean): { head: Line | null; lines: string[] } {
  const old = b.kind ? justBuilt(b.kind, { workflow: b.workflow, t: b.t, map: b.map, next: b.next }) : null;
  if (!auto) return { head: old, lines: [] };
  const head = b.kind === "workflow" ? (b.ready ? autoHead(b.workflow, b.ready) : null) : old;
  return { head, lines: b.ready ? pLines(b.ready) : [] };
}
