// NOW's room (3.6.0.13 L2b, R6): a member's NOW (and main's on Auto) holds two rows from its first draw; longer words grow
// the box ONCE, when the drawing is not held (hold.ts), and it keeps that height for the helper's life (main's: the
// session's); while held, and for later words needing more than it has, NOW reads the held form "a tool · {s}" (one row)
// and the whole words go to the hover at once. The state line "{model} · {state}" holds the rows of its longest words
// ("waiting on you") from the first draw too, so a member never grows when it starts waiting. Text is 12 px mono: 7.2 px a
// character; the seconds sit in their 10ch slot. Pure: no React, no DOM (tests/test_map_groups.py runs it in node).
import { WAIT_WORD } from "../live/waits";
import { countParts, doneLine, STATE_WORDS } from "./groupWords";
import type { AutoGroup } from "./overlayGroups";
import { waitWhat } from "./truth";
import { toolClock, waitClock } from "./truthBits";

export const CHAR_PX = 7.2;
const SECS_CH = 10;
/** NOW's kept rows: `grown` once it has used its one growth. */
export type Kept = { rows: number; grown: boolean };
export type Fit = { text: string; secs: string; rows: number; kept: Kept };

export const perRow = (width: number): number => Math.max(1, Math.floor(width / CHAR_PX));
export const rowsOf = (text: string, secs: string, width: number): number =>
  Math.max(1, Math.ceil((text.length + (secs ? SECS_CH : 0)) / perRow(width)));
/** The rows NOW's longest words but a tool's need ("waiting for a model reply · {s}"), at most two. */
export const heldRows = (width: number): number => Math.min(2, rowsOf(waitClock(waitWhat("model"), ""), "s", width));
/** The state line's held rows: "{model} · waiting on you" (the longest state word). */
export const stateRows = (model: string, width: number): number =>
  rowsOf(model ? `${model} · ${STATE_WORDS.waiting}` : STATE_WORDS.waiting, "", width);

/** 3.6.0.15 F1: the rows a line takes at `width` when it breaks at its spaces, as a group's counts line does (greedy,
 *  perRow characters a row; a word longer than a row breaks inside it, as `overflow-wrap: anywhere` does; a no-break
 *  space never breaks). NOW's rows stay rowsOf's. */
export function wrapRows(text: string, width: number): number {
  const per = perRow(width);
  let rows = 1, used = 0;
  for (const word of text.split(" ")) {
    if (used && used + 1 + word.length <= per) { used += 1 + word.length; continue; }
    if (used) rows += 1;
    rows += Math.max(0, Math.ceil(word.length / per) - 1);
    used = word.length % per || (word.length ? per : 0);
  }
  return rows;
}
const COST_CH = 8; // the cost part of the longest form: "<$0.0001", "$0.0400", "$123.45" all fit eight characters
const COUNTED = ["running", "queued", "waiting", "done", "stopped", "failed"]; // every raw state countParts counts
const standIn = (raws: string[], ended: number): AutoGroup => ({ n: 0, key: "", by: "task", name: "", first: 0,
  members: raws.map((raw, i) => ({ aid: `${i}`, parent: "", who: "", description: "", model: "", state: "idle", raw, cost: 1,
                                    reason: "", made: false, started: 1, ended })) });
/** F1: the counts line's held rows for a group of `members` at text `width`: the rows of its LONGEST form (every part
 *  present, each count written as `members`, the cost eight characters) or of its all-done form at "59 min". */
export function countsRows(members: number, width: number): number {
  const k = Math.max(1, members), cost = "$".padEnd(COST_CH, "0");
  const parts = countParts(standIn(COUNTED, 0)).map((p) => p.text);
  const all = [...parts.slice(0, -1).map((t) => t.replace(/^\d+/, String(k))), cost].join(" · ");
  const done = doneLine(standIn(Array(k).fill("done"), 1 + 59 * 60)).replace(/\S*\$\S*/, cost);
  return Math.max(wrapRows(all, width), wrapRows(done, width));
}

/** NOW `now` in a text `width` with its kept rows, `held` while the drawing is held: the words drawn and the rows kept. */
export function nowFit(now: { text: string; secs: string }, width: number, kept: Kept, held: boolean): Fit {
  const k: Kept = { rows: Math.max(kept.rows, heldRows(width)), grown: kept.grown };
  const need = rowsOf(now.text, now.secs, width);
  if (need <= k.rows) return { text: now.text, secs: now.secs, rows: k.rows, kept: k };
  if (!held && !k.grown) return { text: now.text, secs: now.secs, rows: need, kept: { rows: need, grown: true } };
  const text = toolClock(WAIT_WORD.tool, "");
  return { text: now.secs ? text : text.replace(/ · $/, ""), secs: now.secs, rows: k.rows, kept: k };
}
