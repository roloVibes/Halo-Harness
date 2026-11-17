// The Prompt panel's words and its pure rules (3.6.0.2 P6, "one prompt"; no imports: node runs it in the tests).
// * `askLabel` is the page's word-for-word copy of THE table, Python's `events.ask_label` (tests/test_studio_prompt_words.py
//   holds the two equal); an answered ask reads `answeredLine(where, label)` in place of its buttons (P23).
// * `keepsSent` / `afterAnswer` are P72: Enter records the text sent; an edit that touches its first characters before
//   the answer drops the record; the answer removes the text only while the record stands (and the box still begins
//   with it), with the spaces and line breaks after it. Nothing is taken out before the answer, nothing is put back.
export const ANSWERED_WORDS: Record<string, string> = {
  terminal: "Answered in the terminal: ",
  studio: "Answered in Studio: ",
  remote: "Answered remotely: ",
};
export const INTERRUPTED = "Interrupted.";
export const STEERING = "↳ steering the running turn…";

const PERMISSION_LABELS: Record<string, string> = { once: "Allow", session: "Allow for this session", always: "Allow always" };

const withWords = (base: string, words: unknown): string => {
  const w = String(words ?? "").trim();
  return w ? `${base}: ${w}` : base;
};

/** How an answer reads (events.ask_label, word for word). */
export function askLabel(kind: string, fields: Record<string, unknown> | null | undefined): string {
  const f = fields && typeof fields === "object" ? fields : {};
  if (kind === "permission") {
    if (f.action === "allow") return PERMISSION_LABELS[String(f.scope || "once")] ?? "Allow";
    return withWords("Deny", f.message);
  }
  if (kind === "question") {
    let answer = f.answer;
    if (answer && typeof answer === "object" && !Array.isArray(answer)) answer = Object.values(answer);
    if (Array.isArray(answer)) return answer.map(String).join("; ");
    return answer === null || answer === undefined ? "" : String(answer);
  }
  if (kind === "plan") return f.approved ? "Approve the plan" : withWords("Keep planning", f.feedback);
  const action = String(f.action || "");
  if (action === "edit") return withWords("Edit, re-run", f.instruction);
  return ({ accept: "Accept", stop: "Stop" } as Record<string, string>)[action] ?? action.slice(0, 1).toUpperCase() + action.slice(1);
}

/** The one line an answered ask shows in place of its buttons. */
export const answeredLine = (where: string, label: string): string => (ANSWERED_WORDS[where] ?? ANSWERED_WORDS.remote) + label;

const samePrefix = (a: string, b: string): number => {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
};

/** P72: does an edit from `prev` to `next`, its selection starting at `editStart` before it, leave the first `len`
 *  characters (the text sent) untouched? Anything unsure answers false: then the answer leaves the box alone. */
export function keepsSent(len: number, prev: string, next: string, editStart: number): boolean {
  return editStart >= len && samePrefix(prev, next) >= len;
}

// The edits whose start is known from the selection before (at beforeinput) and the caret after (at input): an
// insert or replace starts at the first, a Backspace-like delete at the second. An undo, a drop, a transpose or a
// spelling replacement can start anywhere: unknown.
const PLAIN_EDIT = /^(insert(Text|LineBreak|Paragraph|FromPaste|FromPasteAsQuotation|FromYank|CompositionText)|delete(Content|Word|SoftLine|HardLine|EntireSoftLine|ByCut)\w*)$/;

/** P72: where an edit began, from its `inputType`, the selection start before it and the caret after it; 0 when unknown. */
export function editStart(inputType: string, before: number | null, after: number): number {
  if (before === null || !PLAIN_EDIT.test(inputType)) return 0;
  return Math.max(0, Math.min(before, after));
}

// P27-P29, P31, P32: the header's words and the lines that stand in their place (THE place they live).
export const NO_MESSAGES = "no messages yet";
export const IN_TERMINAL = "in a terminal";
export const NO_TERMINAL = "no terminal";
export const CHANGE_SESSION = "Change session";
export const ENDED = "This session has ended. What you typed is still here.";
export const COPY = "Copy";
export const COPIED = "Copied.";
export const LINE_MS = 6000; // P29, P31: the line shows this long in the header's place
export const COPIED_MS = 2000;

/** What the header reads of a session's row (fleet/types.ts SessionRow). */
export type HeadRow = { cwd?: string | null; title?: string | null; first_words?: string | null; started?: number | null; kind?: string | null };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const two = (n: number): string => String(n).padStart(2, "0");

/** The folder's own name (`/work/app` and `C:\work\app\` both give `app`). */
export const folderOf = (cwd: string | null | undefined): string => String(cwd || "").split(/[\\/]+/).filter(Boolean).pop() || String(cwd || "");

/** P27: the title, else the first words and …, else `no messages yet`; never an id. */
export function titleOf(row: HeadRow): string {
  const t = String(row.title || "").trim();
  if (t) return t;
  const w = String(row.first_words || "").trim();
  return w ? `${w}…` : NO_MESSAGES;
}

/** P27: `started 09:10` today, `started Nov 16, 09:10` on another day ("" with no start time); `now` in ms. */
export function startedWords(started: number | null | undefined, now: number): string {
  const s = Number(started) || 0;
  if (!s) return "";
  const d = new Date(s * 1000), n = new Date(now);
  const hm = `${two(d.getHours())}:${two(d.getMinutes())}`;
  const today = d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
  return `started ${today ? hm : `${MONTHS[d.getMonth()]} ${d.getDate()}, ${hm}`}`;
}

/** P27: the header's four parts (the page colours each); `headLine` joins them with ` · `. */
export function headParts(row: HeadRow, now: number): { folder: string; title: string; started: string; terminal: string } {
  return { folder: folderOf(row.cwd), title: titleOf(row), started: startedWords(row.started, now), terminal: row.kind === "headless" ? NO_TERMINAL : IN_TERMINAL };
}
export const headLine = (row: HeadRow, now: number): string => Object.values(headParts(row, now)).filter(Boolean).join(" · ");

/** P29: the pick changed by anything but the list; `short` when the title would not fit the header's height. */
export const movedLine = (row: HeadRow, short: boolean): string =>
  short ? `Now typing into ${folderOf(row.cwd)}.` : `Now typing into ${folderOf(row.cwd)} · ${titleOf(row)}.`;
/** P31: the pick followed the terminal to its new conversation. */
export const followLine = (row: HeadRow): string => `Same terminal, new conversation: ${folderOf(row.cwd)}.`;

/** P72: the box once the answer to a send arrives while its record stands: `null` leaves the box as it is. */
export function afterAnswer(box: string, sent: string): string | null {
  if (!box.startsWith(sent)) return null;
  if (!sent) return box; // P7: an image-only send sent no text: what he typed after it stays exactly
  return box.slice(sent.length).replace(/^\s+/, "");
}
