// The other lines the new drawings show (3.6.0.2 section 4: "Other strings are in their rules"), letter for letter, one
// function per rule's line: R4 the Start view, R14 a workflow's block, R15 the rows in a box, R16 a trace's hover, R17 an
// off-map line's hover, R18 the step-in card, R24 Agents -> Map's picker, R28 a removed map, R29 the tag, R30 the pair, R31
// the Just built heads, R43 the hover card, R45 the unreached band, R47 the Workflows head. Re-exported by truth.ts; the
// Session and Agents builders read them from there. Every {t} through clock(), every word Live / Map through WORDS. Pure.
import { clock, NEXT_NONE, nextName, WORDS, type Line } from "./truthWords";

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** R4 the Start view (no session row): the first sentence; the last build seen from a since-ended session, its second
 *  sentence only when that map is the one new sessions use; [New session] on the last line. */
export function startLines(b: string | null, last: { map: string; t: number } | null, none = false): Line[] {
  const out: Line[] = [{ text: none ? `No session is open here. ${NEXT_NONE}` : `No session is open here. New sessions will run on ${nextName(b)}.` }];
  if (last) out.push({ text: `Your last session built the map ${last.map} at ${clock(last.t)}.${b === last.map ? " New sessions run on it." : ""}` });
  out[out.length - 1] = { ...out[out.length - 1], act: "new-session", label: "New session" };
  return out;
}

/** R14 a saved workflow's block: its head (with the step while it runs) and one row per step, every step. */
export const blockHead = (workflow: string, step?: number, of?: number): string =>
  step && of ? `workflow ${workflow} · step ${step} of ${of}` : `workflow ${workflow}`;
export const stepRow = (i: number, step: string, agent: string, model: string, state: "done" | "working" | "next" | "failed" | string): string =>
  [`${i} ${step}`, agent, model, state].filter(Boolean).join(" · "); // a model (or agent) not known yet is left out, never "· ·"

/** R15 the other children inside their box: a saved agent, one made up for a task (its first 40 characters), the rest. */
export const agentRow = (agent: string, model: string, state: string): string => `${agent} · ${model} · ${state}`;
export const madeUpRow = (task: string, state: string): string => `made up: ${task.slice(0, 40)} · ${state}`;
/** A box's rows past the third (R15; P4 batch 13: the 3.6.0.0 door to the Feed's `under:` page): "+{n} under it". */
export const moreRows = (n: number): string => `+${n} under it`;
/** P4 batch 13: the tool clock of a working box or row -- the tool it is in and for how long ("Bash · 12 s"). */
export const toolClock = (tool: string, secs: string): string => `${tool} · ${secs}`;

/** R16 a trace's hover: the hand-offs it carried, the last one's time and few words. */
export const traceHover = (n: number, t: number, words: string): string =>
  `Carried ${plural(n, "hand-off", "hand-offs")}; last at ${clock(t)}: ${words}`;

/** R17 an off-map line's hover. */
export const offHover = (sender: string): string => `Not on the map: ${sender} started this itself`;

/** R18 the step-in card: an ended agent, an off-map line's link, the link every card has. */
export const endedAt = (t: number): string => `ended at ${clock(t)}`;
export const openMapAt = (sender: string): string => `Open the map at ${sender}`;
export const openInAgents = (): Line => ({ text: "", act: "open-agents-live", label: `Open in Agents -> ${WORDS.live}` });

/** R24 Agents -> Map's picker: the sessions running a map (F2), the map new sessions use (F4); the switch. */
export function pickerSuffix(running: string[], next = false): string {
  const run = running.length === 1 ? ` · running in ${running[0]}` : running.length > 1 ? ` · running in ${running.length} sessions` : "";
  return run + (next ? " · new sessions" : "");
}
export const switchLabel = (): string => "New sessions run on this";
/** R36's use-row words, and the hand switch's receipt with no session open (R55). */
export const newSessionsRunOn = (b: string): string => `New sessions run on ${b}.`;
/** R55 L3: the mark on the workflow's box on Agents -> Map. */
export const runningNowIn = (session: string): string => `running now in ${session}`;

/** R28 a run's map not read yet (its drawing waits; the head above it is drawn from the row). */
export const readingMap = (name: string): string => `Reading the map ${name}...`;

/** R28 a just-built map that is gone. */
export const removedAt = (t: number): string => `This map was removed at ${clock(t)}.`;

/** R29 the tag on boxes and block rows this build wrote. */
export const newTag = (t: number): string => `new ${clock(t)}`;

/** R30 the two maps in the drawer. */
export const pair = (running: string, built: string): [string, string] => [`Running: ${running}`, `Just built: ${built}`];

/** R31 the Just built heads: a workflow on no map, a change to the running map, any other map (+ R36's row when the
 *  build made it the map new sessions run on, `next`; its S13 is the truth block's T2 line just above). */
export function justBuilt(kind: "workflow" | "running" | "other", o: { workflow?: string; t?: number; map?: string; next?: string | null }): Line {
  if (kind === "workflow")
    return { text: `Just built: the workflow ${o.workflow}. It is on no map, so no session runs it yet.`, act: "open-workflows", label: "Open in Workflows" };
  if (kind === "running") return { text: `Changed in this session at ${clock(o.t || 0)}; this session takes it at its next hand-off.` };
  // R31 "(+ R36's row)": the row WITHOUT S13, as the coordinator ruled: S13 is on screen once, in the truth block just
  // above this head (its T2 line), never twice in the drawer
  const use = o.map && o.next === o.map ? ` New sessions run on ${o.map}.` : "";
  return { text: `Just built in this session at ${clock(o.t || 0)}. This session does not run on it.${use}` };
}

/** R43 one line that feeds a box (a box fed by several lines has one row per line); R18's state of a calm line. */
export const startsWhen = (when: string, source: string): string => `Starts when: ${when} (from ${source})`;

/** R43 the hover card on a Session box (hover = summary; a click opens R18's card). `more`: the other lines feeding it,
 *  [when, source] each; main (fed by no line) has no "Starts when" row. */
export function hoverLines(h: { name: string; workflow: string | null; model: string; state: string; when: string; source: string;
  children: string[]; built: number | null; more?: [string, string][] }): string[] {
  const starts = h.source ? [[h.when, h.source], ...(h.more || [])].map(([w, s]) => startsWhen(w, s)) : [];
  const out = [h.name, h.workflow ? `workflow ${h.workflow}` : "agent", h.model, h.state, ...starts, ...h.children].filter((x) => x !== "");
  if (h.built) out.push(`Built ${clock(h.built)} in this session`);
  return out;
}

/** R45 the heading over the boxes no line from main reaches. */
export const unreachedHead = (): string => "Not connected yet: no line from main reaches these, so this session never runs them.";

/** R47 what the Workflows head adds. */
export const workflowsHead = (): string =>
  `Workflows are fixed lists of steps. A session runs a map, and a box on a map can run a workflow: see ${WORDS.map}.`;

/** P4 batch 9: an ask's door pressed after its session ended (glance/openAsk.ts), one line; `t` 0 when not seen ending. */
export const askEnded = (t: number): string =>
  `This session ${t ? `ended at ${clock(t)}` : "has ended"}. Nothing waits on you there now.`; // T8's first sentence (P4 batch 12)
/** P4 batch 12 (the owner's point 24): an ask's door for an agent the drawing puts on no box (glance/openAsk.ts). */
export const askOffMap = (agent: string): string => `${agent} is not on the map: its question is in the ${WORDS.feed}.`;
