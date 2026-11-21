// What a Copy button copies (3.6.0.6 C, the owner: "Copying from the session barely works!"): a reply's SOURCE (the
// text as the agent wrote it) and each fenced code block's code only (its indentation and line breaks kept, no fence
// lines). `segments` splits a reply into its prose and its code blocks without losing a character: joined back
// (`joined`) they are the reply again, so a row draws the reply as written with a Copy beside each block.
// Pure (no React): tests/test_copy_button_ui.py runs it under node.

/** The button's words: what it says, then for two seconds after a press, or when the browser refused the clipboard. */
export const COPY = "Copy";
export const COPIED = "Copied";
export const COPY_REFUSED = "Select and copy it yourself";
export const COPIED_MS = 2000;

export type Prose = { code: false; text: string };
/** `open`: the opening fence line as written ("```python"); `body`: the code only; `close`: the closing fence line
 *  ("" while a streaming reply has not closed it yet); `nl`: the line breaks around the code, as written. */
export type Code = { code: true; open: string; body: string; close: string; nl: [string, string] };
export type Segment = Prose | Code;

const FENCE = /^[ \t]*(```|~~~)[ \t]*[\w+.-]*[ \t]*$/;

/** The reply as prose and code blocks, every character kept (`joined(segments(t)) === t`). */
export function segments(src: string): Segment[] {
  const text = String(src || "");
  const out: Segment[] = [];
  const lines = text.split(/(\r?\n)/); // [line, break, line, break, ..., line]
  let prose = "";
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const m = FENCE.exec(line);
    if (!m) {
      prose += line + (lines[i + 1] ?? "");
      i += 2;
      continue;
    }
    const marker = m[1];
    const closes = (l: string) => l.trim().startsWith(marker) && /^[`~]+$/.test(l.trim());
    let j = i + 2;
    while (j < lines.length && !closes(lines[j])) j += 2;
    const closed = j < lines.length;
    if (prose) out.push({ code: false, text: prose });
    prose = "";
    // between the fences: line, break, ..., line (the break before the closing fence is `nl[1]`)
    const body = lines.slice(i + 2, closed ? j - 1 : lines.length).join("");
    out.push({ code: true, open: line, body, close: closed ? lines[j] : "", nl: [lines[i + 1] ?? "", closed && j > i + 2 ? lines[j - 1] : ""] });
    if (!closed) break;
    prose = lines[j + 1] ?? "";
    i = j + 2;
  }
  if (prose) out.push({ code: false, text: prose });
  return out;
}

/** The segments back as the reply (a test's proof that nothing was lost). */
export function joined(segs: Segment[]): string {
  return segs.map((s) => (s.code ? s.open + s.nl[0] + s.body + s.nl[1] + s.close : s.text)).join("");
}

/** Each code block's code, in order: what each block's Copy puts on the clipboard. */
export function codeBlocks(src: string): string[] {
  return segments(src).flatMap((s) => (s.code ? [s.body] : []));
}

/** A reply's Copy: the text as the agent wrote it, nothing added, nothing cut. */
export const replySource = (l: { text?: string }): string => String(l.text || "");
