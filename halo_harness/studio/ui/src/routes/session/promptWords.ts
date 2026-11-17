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

/** P72: the box once the answer to a send arrives while its record stands: `null` leaves the box as it is. */
export function afterAnswer(box: string, sent: string): string | null {
  if (!box.startsWith(sent)) return null;
  return box.slice(sent.length).replace(/^\s+/, "");
}
