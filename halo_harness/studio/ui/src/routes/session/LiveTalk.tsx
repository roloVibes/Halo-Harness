// A TALK row's body (3.3.16.2, the owner: "we see models conversing with each other and that's its own label"): the
// row's tag is the speaker; the body starts with an arrow and the listener's tag (an agent of the session, or the
// machine a hand-over went to), the reason as a small mono caps word (TASK, HAND-BACK, STEER, SQUARE, HAND-OVER),
// then the words clamped to four lines with "show all". A hand-back is drawn as the OUT block it replaces (one row:
// liveTalk.ts), so the user's "done, its last words" and the parent's message are the same row.
import type { LiveLine } from "../shared/liveFeed";
import { hueOf } from "../shared/hues";
import { Clamp } from "./LiveThink";

export const WHY_WORD: Record<string, string> = { task: "TASK", "hand-back": "HAND-BACK", steer: "STEER", square: "SQUARE", "hand-over": "HAND-OVER" };

export function TalkHead({ l }: { l: LiveLine }) {
  const t = l.talk!;
  const to = t.toKey ? t.toName : `${t.toName || t.machine || "?"} (another machine)`;
  return (
    <div className="slv-talk-head mono">
      <span className="slv-talk-arrow" aria-hidden="true">→</span>
      <span className="slv-talk-to" data-testid="live-talk-to" data-hc={t.toKey ? hueOf(t.toKey) : undefined} data-key={t.toKey || undefined} title={`to ${to}`}>
        {to}
      </span>
      <span className="slv-talk-why" data-testid="live-talk-why">{WHY_WORD[t.why] || t.why.toUpperCase()}{t.square ? ` · ${t.square}` : ""}</span>
      {t.re && <span className="slv-talk-re muted" title="It answers an earlier message">reply</span>}
    </div>
  );
}

export function TalkBody({ l }: { l: LiveLine }) {
  if (!l.talk) return null;
  const cut = l.talk.cut ? ` (the first ${l.text.length} of ${l.talk.chars || "more"} characters: the transcript has it all)` : "";
  const back = l.talk.why === "hand-back";
  return (
    <div className={back ? "slv-talk slv-out" : "slv-talk"} data-why={l.talk.why} data-state={back ? "done" : undefined} data-testid="live-talk">
      <TalkHead l={l} />
      <Clamp text={l.text + cut} className="slv-talk-text" testid="live-talk-text" />
    </div>
  );
}
