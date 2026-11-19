// The words of Auto's groups (3.6.0.5 B9 B11 B13 B30, section 3 (b)), letter for letter, one function per line: a group's
// counts line (zero parts left out, "{f} failed" its own part so the page draws it in --bad) and its all-done form, a
// member's two lines (and a child of a child's third), "+{n} more", the hovers G3 (a group's head), G4 (a member) and G5
// (main on Auto). Pure: no React, no DOM, no store, no clock of its own (tests/test_map_groups.py runs it in node).
// STATE_WORDS lives here (LitBits.tsx re-exports it) so the words of a box's state are written once.
import { whyOf } from "../live/groups";
import type { BoxState } from "./overlay";
import type { AutoGroup, Member } from "./overlayGroups";
import { waitWhat } from "./truth";
import { waitClock, whyThisModel } from "./truthBits";
import { clock } from "./truthWords";

export const STATE_WORDS: Record<BoxState, string> = { working: "working", waiting: "waiting on you", done: "done", failed: "failed", idle: "not used yet" };

export const SHOWN_MEMBERS = 8; // B11: up to 8 members shown, then "+{n} more"
const NAMES_SHOWN = 12; // G5: twelve names, then "and {n} more"

export const money = (x: number): string => `$${(Number(x) || 0).toFixed(2)}`;
/** r/batch04 entry 3: a number and its unit are held by a no-break space, so a narrow box never tears "0" from "s". */
const NB = " ";
/** "{m} min" from 60 s (whole minutes, rounded down), else "{s} s". Every group line, member line and hover takes its
 *  spans from here. */
export const span = (s: number): string => {
  const t = Math.max(0, Math.floor(Number(s) || 0));
  return t >= 60 ? `${Math.floor(t / 60)}${NB}min` : `${t}${NB}s`;
};
const agents = (k: number): string => `${k} ${k === 1 ? "agent" : "agents"}`;
const cost = (g: AutoGroup): number => g.members.reduce((s, m) => s + (Number(m.cost) || 0), 0);
const allDone = (g: AutoGroup): boolean => g.members.length > 0 && g.members.every((m) => m.state === "done");

/** The counts line's parts, in order: agents, working, waiting, done, failed (`bad`), cost; a part that is zero is left out. */
export function countParts(g: AutoGroup): { text: string; bad?: boolean }[] {
  const n = (st: BoxState) => g.members.filter((m) => m.state === st).length;
  const out: { text: string; bad?: boolean }[] = [{ text: agents(g.members.length) }];
  const [w, v, d, f, c] = [n("working"), n("waiting"), n("done"), n("failed"), cost(g)];
  if (w) out.push({ text: `${w} working` });
  if (v) out.push({ text: `${v} waiting` });
  if (d) out.push({ text: `${d} done` });
  if (f) out.push({ text: `${f} failed`, bad: true });
  if (c > 0) out.push({ text: money(c) });
  return out;
}

/** "{k} agents · all done · ${cost} · {time}": the time from the first member's start to the last member's end. */
export function doneLine(g: AutoGroup): string {
  const start = Math.min(...g.members.map((m) => m.started || Infinity));
  const end = Math.max(...g.members.map((m) => m.ended || m.started || 0));
  const t = isFinite(start) && end > start ? end - start : 0;
  return `${agents(g.members.length)} · all done · ${money(cost(g))} · ${span(t)}`;
}

/** The head's second line: the all-done form when every member is done, else the counts. */
export const countsLine = (g: AutoGroup): string => (allDone(g) ? doneLine(g) : countParts(g).map((p) => p.text).join(" · "));
export const isAllDone = allDone;

/** The head's why line (`whyOf`, Auto only): "" when no member carries a pick's reason. */
export const whyLine = (g: AutoGroup): string =>
  whyOf(g.members.map((m) => ({ role: m.who, name: m.who, model: m.model, reason: m.reason })));

/** B11 a member: "{who}: {description}" ("{who}" alone without one) over "{model} · {state}" ("{state}" without a model). */
export const memberLine = (m: Member): string => (m.description ? `${m.who}: ${m.description}` : m.who);
export const memberState = (m: Member): string => (m.model ? `${m.model} · ${STATE_WORDS[m.state]}` : STATE_WORDS[m.state]);
/** B2 a child of a child's third line: its parent member's who and description. */
export const startedBy = (who: string, task: string): string => `started by ${who}: ${task}`;
export const moreMembers = (n: number): string => `+${n} more`;
/** B26 the slot at the drawing's foot: a working group wholly out of sight, and how many other boxes wait below. */
export const belowGroup = (name: string, more: number): string => `↓ ${name} · working${more > 0 ? ` and ${more} more below` : ""}`;
/** b/batch08: the name Session's slot on Auto keeps room for (its hidden twin): a long name of ordinary letters, 60 characters. */
export const BELOW_SAMPLE = "compare the three reports and write the summary for the team";
/** k/batch02 entry 1: main's box on Auto holds the room of its fullest state from the first draw -- a hidden twin of its
 *  row while it works on a usual tool, and of the clock while it waits for a model reply (LitMini.tsx LitFace). */
export const MAIN_HOLD = { row: `main · ${STATE_WORDS.working} · Agent read the report`, clock: waitClock(waitWhat("model"), ""), secs: "59 s" };
/** The third line of member `m` of group `g` ("" for a child of main). */
export function thirdLine(g: AutoGroup, m: Member): string {
  if (!m.by) return "";
  const p = g.members.find((x) => x.aid === m.by);
  return p ? startedBy(p.who, p.description || p.who) : "";
}

/** G3, a group's head hovered: its name, when main started it, one line per member, its cost. */
export function g3Lines(g: AutoGroup): string[] {
  return [g.name, `Started by main at ${clock(g.first)}`,
    ...g.members.map((m) => [m.who, m.model, STATE_WORDS[m.state]].filter(Boolean).join(" · ")), money(cost(g))];
}

/** G4, a member hovered: its description, who on which model, why that model, its state, cost and time (`now`: seconds). */
export function g4Lines(m: Member, now = 0): string[] {
  const end = m.ended || (m.state === "working" || m.state === "waiting" ? now : 0);
  const time = m.started && end >= m.started ? span(end - m.started) : "";
  return [m.description || m.who, m.model ? `${m.who} on ${m.model}` : m.who, whyThisModel(m.reason),
    [STATE_WORDS[m.state], money(m.cost), time].filter(Boolean).join(" · ")].filter((x) => x !== "");
}

/** G5, main hovered on Auto: its model and the agents this session started with (its row's `map_agents`, A22). */
export function g5Lines(model: string, names: string[]): string[] {
  const head = model ? `main · ${model}` : "main";
  if (!names.length) return [head];
  const shown = names.slice(0, NAMES_SHOWN).join(", "), more = names.length - NAMES_SHOWN;
  return [head, `Can hand work to: ${shown}${more > 0 ? ` and ${more} more` : ""}`];
}
