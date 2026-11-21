// The one Copy button (3.6.0.6 C, the owner: "Copying from the session barely works!"): on every reply and every code
// block of Session's Live column and of the Prompt panel's feed. It shows on hover and on keyboard focus (a tab stop),
// in room that is there from the first draw: the button is as wide as its longest word at all times (the other words
// are drawn invisible in the same cell, from CSS, so they are no text of the page), so nothing moves when it shows or
// when its word changes. A press puts the SOURCE on the page's clipboard (`text`: a reply as the agent wrote it, a
// block's code only) and reads "Copied" for two seconds in the same place: no toast, no pop-up. When the browser
// refuses the clipboard it reads "Select and copy it yourself" and selects the text (`of`) for him.
import { useEffect, useRef, useState } from "react";
import { COPIED, COPIED_MS, COPY, COPY_REFUSED } from "../copyText";

type Said = "copy" | "copied" | "refused";
const WORDS: Record<Said, string> = { copy: COPY, copied: COPIED, refused: COPY_REFUSED };
const REFUSED_MS = 6000; // long enough to read; the selection he was given stays

/** The text of `el` selected, as a drag over it would select it. */
function selectText(el: Element | null | undefined): void {
  const sel = window.getSelection();
  if (!el || !sel) return;
  const r = document.createRange();
  r.selectNodeContents(el);
  sel.removeAllRanges();
  sel.addRange(r);
}

type Props = { text: () => string; of: () => Element | null | undefined; testid: string; title: string };

export function CopyButton({ text, of, testid, title }: Props) {
  const [said, setSaid] = useState<Said>("copy");
  const timer = useRef(0);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const settle = (s: Said, ms: number) => {
    setSaid(s);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setSaid("copy"), ms);
  };
  const refused = () => {
    settle("refused", REFUSED_MS);
    selectText(of());
  };
  const press = () => {
    try {
      const cb = navigator.clipboard;
      if (!cb || typeof cb.writeText !== "function") return refused();
      cb.writeText(text()).then(() => settle("copied", COPIED_MS), refused);
    } catch {
      refused();
    }
  };
  return (
    <button type="button" className="copy-btn mono" data-testid={testid} data-said={said === "copy" ? undefined : said} onClick={press}
            title={title} aria-live="polite">
      <span className="copy-word" data-on="">{WORDS[said]}</span>
      {Object.values(WORDS).map((w) => <span key={w} className="copy-word copy-room" data-word={w} aria-hidden="true" />)}
    </button>
  );
}
