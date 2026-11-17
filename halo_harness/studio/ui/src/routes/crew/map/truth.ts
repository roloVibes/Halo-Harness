// Every sentence a person reads about which map a session runs on (3.6.0.2 R19, section 4 of the design), letter for
// letter, in ONE place: the truth states T1-T12 and Empty, S13 and its terminal tail, the status line, Agents -> Map's
// lines L1-L4 and the worst case the truth block reserves (R20). The other lines of the rules (R4, R14-R18, R24, R28-R31,
// R43, R45, R47) are in truthBits.ts, re-exported here. Pure: no React, no store, no DOM. The words Live / Feed / Map live
// in truthWords.ts (decision 5), re-exported here; Session, Agents -> Live, Agents -> Map and the Start view read only this.
import { clock, DEFAULT_MAP, mapName, nextName, WORDS, type Line } from "./truthWords";

export * from "./truthWords";
export * from "./truthBits";

/** What the truth block knows of a session (the status row, P2): never `busy` or an agent's state for the sentence. */
export type TruthFacts = {
  none?: boolean; // no session row: the Start view's Empty
  title: string;
  a: string | null; // the map this session runs on (F1/F2); null = no map
  plain: boolean; // it took starter by default (the row's `map_plain`)
  b: string | null; // the map new sessions use (F4); null = unset (starter, the default)
  bSince: number | null; // when B was switched on; null = not known
  started: number;
  turns: number;
  studio: boolean; // its parent is `studio:<pid>`
  ended: number | null;
  machine: string | null; // it runs on another machine
  unreadable: string | null; // the path of a map Studio cannot read here
  changed: { t: number; problem?: string } | null; // its own map changed while it runs (T5 / T6)
  workflow: string | null; // a workflow it runs that is a box on B (T7)
  busy: boolean; // never decides anything here (point 8: the sentence does not flip when a turn ends)
};
export type TruthState = "Empty" | "T1" | "T2" | "T3" | "T4" | "T8" | "T9" | "T10" | "T11" | "T12";

const NEW: Pick<Line, "act" | "label"> = { act: "new-session", label: "New session" };

/** S13 (R21): {old} and {next} are names as a person reads them (`mapName`); the terminal adds its tail. */
export function s13(old: string, next: string, terminal = false): string {
  const s = `This session keeps running on ${old}, as it started. Start a new session to run on ${next}.`;
  return terminal ? `${s} In the terminal: quit and run halo again; /clear keeps ${old}.` : s;
}

/** The map new sessions use, by identity: none set is the default, starter (R19, R20: T1 only when it IS {A}). */
export const nextMap = (b: string | null): string => b || "starter";

/** Which state the truth block is in: read from whether the session is open and its maps, never from `busy`. A session
 *  on its own map while new sessions use another (none set: starter) is T2, or T11 when a set {B}'s time is not known. */
export function truthState(f: TruthFacts): TruthState {
  if (f.none) return "Empty";
  if (f.machine) return "T9";
  if (f.ended) return "T8";
  if (f.studio && !f.turns) return "T10";
  if (f.unreadable) return "T12";
  if (!f.a) return "T4";
  if (f.a !== nextMap(f.b)) return f.bSince || !f.b ? "T2" : "T11";
  return f.plain ? "T3" : "T1";
}

/** The truth block's lines, in R20's order: T7, S13 (or T1 / T3), the started line, T5 / T6. */
export function truthLines(f: TruthFacts): Line[] {
  const st = truthState(f);
  const A = f.a ? mapName(f.a, f.plain) : "";
  const B = nextName(f.b);
  const t = clock(f.started);
  switch (st) {
    case "Empty": return [{ text: `No session is open here. New sessions will run on ${B}.`, ...NEW }];
    case "T9": return [{ text: f.a ? `${f.title} runs on ${A} on ${f.machine}. Its drawing is in that machine's Studio.`
                                   : `${f.title} runs with no map on ${f.machine}. Its drawing is in that machine's Studio.` }];
    case "T8": return [{ text: `This session ended at ${clock(f.ended || 0)}. ${f.a ? `It ran on ${A}.` : "It ran with no map."}` }];
    case "T10": return [{ text: `New session from Studio, no message yet. It will run on ${B}.` }];
    case "T12": return [{ text: `This session runs on ${A} from ${f.unreadable}, which Studio cannot read here.` }];
    case "T4": return [{ text: `This session runs with no map, as it started at ${t}: main does the work and starts its own agents.` }];
  }
  const out: Line[] = [];
  if (f.workflow) out.push({ text: `This session is running the workflow ${f.workflow} from ${B}.` });
  if (st === "T2" || st === "T11") {
    out.push({ text: s13(A, B), ...NEW });
    // T2's "before {B} was switched on" only when it was (none set and never switched: just when it started)
    const before = !!f.bSince && f.bSince > f.started;
    out.push({ text: st === "T11" ? `It started at ${t}. ${B} was set outside Halo, so when it was switched on is not known.`
                                  : before ? `It started at ${t}, before ${B} was switched on at ${clock(f.bSince || 0)}.` : `It started at ${t}.` });
  } else if (st === "T3") {
    out.push({ text: `This session runs on ${DEFAULT_MAP}, as it started at ${t}. On starter main chooses who to hand work to; the dashed lines show what it chose.` });
  } else {
    out.push({ text: `This session runs on ${A}, as it started at ${t}. New sessions will too.` });
  }
  const c = f.changed;
  if (c) out.push({ text: c.problem ? `${A} changed at ${clock(c.t)} but has a problem, so this session keeps the last good version: ${c.problem}.`
                                   : `${A} changed at ${clock(c.t)}; this session takes it at its next hand-off.` });
  return out;
}

/** About how many 12 px text lines `lines` take at the drawer's `width` (7 px a character, 12 px padding each side; a
 *  button's label counts with its frame). It only CHOOSES the longest text; the truth block measures its hidden twin. */
export function est(lines: Line[], width: number): number {
  const w = Math.max(1, width - 24);
  return lines.reduce((n, l) => n + Math.ceil(((l.text.length + (l.label ? l.label.length + 4 : 0)) * 7) / w), 0);
}

/** R20's worst case, with the coordinator's ruling (P4 batch 11): of the states this session can reach with the names it
 *  HAS -- its own {A}, {B} and {W} (T1 / T3, T2 and T11 when B differs, each with and without T7 when a {W} is known and
 *  with and without T5, then T8, then the state it is in now) -- the lines that take the most room at `width`. Nothing is
 *  held for a name it does not have: a {B} switched on later or a {W} that starts later is a real change, and the truth
 *  block measures its twin again then (TruthBlock.tsx). Ties go to the longer text, then to the first. T6's problem is not
 *  known in advance: the block grows for it (R12). */
export function reserve(f: TruthFacts, width: number): { lines: Line[]; est: number } {
  const open: TruthFacts = { ...f, none: false, machine: null, ended: null, unreadable: null, studio: false, turns: Math.max(1, f.turns) };
  const after = (f.bSince && f.bSince > f.started ? f.bSince : f.started + 60) || 60;
  const bs: Partial<TruthFacts>[] = [{ b: f.a }];
  if (f.a && f.a !== nextMap(f.b)) bs.push({ b: f.b, bSince: after }, ...(f.b ? [{ b: f.b, bSince: null }] : []));
  const cands: Line[][] = [];
  for (const b of bs) for (const workflow of f.workflow ? [f.workflow, null] : [null])
    for (const changed of [{ t: f.changed?.t || f.started }, null]) cands.push(truthLines({ ...open, ...b, workflow, changed }));
  cands.push(truthLines({ ...open, ended: f.ended || f.started }), truthLines(f));
  const size = (ls: Line[]) => ls.reduce((n, l) => n + l.text.length + (l.label || "").length, 0);
  let best = cands[0], most = est(best, width);
  for (const c of cands.slice(1)) {
    const e = est(c, width);
    if (e > most || (e === most && size(c) > size(best))) [best, most] = [c, e];
  }
  return { lines: best, est: most };
}

/** One session as Agents -> Map's lines name it. */
export type MapOn = { session: string; a: string; plain: boolean };
export type MapLineFacts =
  | { kind: "L1"; session: string } // a session runs on the open map
  | { kind: "L2"; on: MapOn[] } // sessions run on other maps, as they started; new sessions run on the open one
  | { kind: "L3"; session: string; workflow: string; a: string; plain: boolean } // it runs a workflow of the open map
  | { kind: "L4"; map: string; session: string; t: number }; // the open map was just built in a session

/** Agents -> Map's one quiet line (R55, R33): L1-L4, the bracketed part a button. */
export function mapLine(m: MapLineFacts): Line[] {
  const watch = (them = false): Pick<Line, "act" | "label"> => ({ act: "watch-live", label: `Watch ${them ? "them" : "it"} in ${WORDS.live}` });
  switch (m.kind) {
    case "L1": return [{ text: `${m.session} runs on this map now.`, ...watch() }];
    case "L2":
      if (!m.on.length) return [];
      if (m.on.length === 1) return [{ text: `${m.on[0].session} runs on ${mapName(m.on[0].a, m.on[0].plain)}, as it started; new sessions run on this map.`, ...watch() }];
      return [{ text: `${m.on.length} sessions run on other maps, as they started; new sessions run on this map.`, ...watch(true) }];
    case "L3": return [{ text: `${m.session} is running the workflow ${m.workflow} from this map. It runs on ${mapName(m.a, m.plain)}, as it started.`, ...watch() }];
    case "L4": return [{ text: `${m.map} was just built in ${m.session} at ${clock(m.t)}.`, act: "open-it", label: "Open it" }];
  }
}

/** What the status line is told: `rows` are the session's agents (main included) with their state. */
export type Status = {
  state: "working" | "idle" | "done";
  rows: { name: string; state: string }[];
  what: string; // a tool's few words
  workflow: { name: string; step: number; of: number } | null;
  waiting: "model" | "you" | string | null; // another string is the agent it waits for
  cost: number;
  off: number; // hand-offs outside the map (0 on starter: there every hand-off is main's pick)
};

/** R23: one status line; who = the rows working now only. */
export function statusLine(s: Status): string {
  const cost = `$${(s.cost || 0).toFixed(2)}`;
  const off = s.off > 0 ? ` · ${s.off} ${s.off === 1 ? "hand-off" : "hand-offs"} outside the map` : "";
  if (s.state === "idle") return `Waiting for you · ${cost}${off}`;
  if (s.state === "done") return `Done · ${cost}${off}`;
  const work = s.rows.filter((r) => r.state === "working");
  const who = work.length > 1 ? `${work.length} agents` : work.length ? work[0].name : "main";
  const what = s.workflow ? `the workflow ${s.workflow.name}, step ${s.workflow.step} of ${s.workflow.of}` : s.what;
  const wait = s.waiting ? ` · waiting for ${s.waiting === "model" ? "a model reply" : s.waiting}` : "";
  return `${who} working${what ? ` on ${what}` : ""}${wait} · ${cost}${off}`;
}

/** R23 with the coordinator's ruling (P4 batch 11): the status sentences this run can show with the names it HAS -- `now`,
 *  the rows' `names` (who), the workflows it knows with their step counts (`flows`), waiting for a model reply or for you,
 *  and a hand-off outside the map unless it runs on the default map (`plainMap`). The status line's hidden twin holds them
 *  all, and the line takes the tallest from its first draw (never less than its two lines), so a sentence that changes
 *  moves nothing under it. */
export function statusRoom(now: Status, names: string[], flows: { name: string; of: number }[], plainMap: boolean): string[] {
  const who = [...new Set(["main", ...names])];
  const rows = [...who.map((name) => [{ name, state: "working" }]), ...(who.length > 1 ? [who.map((name) => ({ name, state: "working" }))] : [])];
  const flowsTo = [null, ...flows.filter((w) => w.name).map((w) => ({ name: w.name, step: Math.max(1, w.of), of: Math.max(1, w.of) }))];
  const offs = plainMap ? [now.off] : [...new Set([now.off, Math.max(1, now.off)])];
  const out = new Set([statusLine(now)]);
  for (const off of offs) {
    for (const state of ["idle", "done"] as const) out.add(statusLine({ ...now, state, off }));
    for (const r of rows) for (const workflow of flowsTo) for (const waiting of [null, "model", "you"])
      out.add(statusLine({ ...now, state: "working", rows: r, what: "", workflow, waiting, off })); // a tool's words are no name
  }
  return [...out];
}
