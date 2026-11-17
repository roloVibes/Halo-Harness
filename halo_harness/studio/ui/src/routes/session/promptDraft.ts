// The Prompt box's text (split from promptStore.ts in 3.6.0.2 to keep it under 250 lines): its history per session,
// kept in this browser (localStorage, try/catch: a private window simply has none), and P72's record of a send.
// 3.6.0.2 P72: at Enter the page records what was sent; an edit, paste, cut or history recall that touches its first
// characters before the answer drops the record; the answer removes text only while it stands (promptWords.ts).
// Nothing is taken out before the answer and nothing is ever put back.
import { prompt } from "./promptStore";
import { afterAnswer, keepsSent } from "./promptWords";
import type { SteerImage } from "./steerImage";

const MAX_HISTORY = 100;
const histKey = (sid: string) => `halo.studio.prompt.history.${sid}`;

export function history(sid: string): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(histKey(sid)) || "[]");
    return Array.isArray(v) ? v.map(String) : [];
  } catch {
    return [];
  }
}

export function pushHistory(sid: string, text: string): void {
  if (!sid || !text.trim()) return;
  try {
    const h = history(sid).filter((x) => x !== text);
    localStorage.setItem(histKey(sid), JSON.stringify([...h, text].slice(-MAX_HISTORY)));
  } catch {
    /* a private window keeps no history */
  }
}

let sent: { text: string | null; img: SteerImage | null } | null = null;

/** Enter: the text and chip on their way (the record stands through the busy line's Queue it / Steer). */
export function recordSent(text: string, img: SteerImage | null): void {
  sent = { text: prompt.get().draft.startsWith(text) ? text : null, img };
}

/** A send that was refused, failed, cancelled or ran nothing: the box stays exactly as it is. */
export const dropSent = (): void => void (sent = null);

/** The answer took the send: the sent text (and the sent chip, while its slot still holds it) leaves the box. */
export function takeSent(): void {
  const s = sent;
  sent = null;
  if (!s) return;
  const st = prompt.get();
  const box = s.text === null ? null : afterAnswer(st.draft, s.text);
  const chip = !!s.img && st.img === s.img;
  if (box !== null || chip) prompt.update(() => ({ ...(box !== null ? { draft: box } : {}), ...(chip ? { img: null, imgError: "" } : {}) }));
}

/** The box's text changed; `editStart`: where the edit's selection began before it (0 when unknown: the record goes). */
export function setDraft(draft: string, editStart = 0): void {
  if (sent && sent.text !== null && !keepsSent(sent.text.length, prompt.get().draft, draft, editStart)) sent = { ...sent, text: null };
  prompt.update(() => ({ draft }));
}
