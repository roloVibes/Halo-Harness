// A reply as the agent wrote it, its fenced code blocks drawn as blocks, each with a Copy of its code only (3.6.0.6 C,
// the owner: "Copying from the session barely works!"). Every character of the reply is drawn (lib/copyText.ts
// segments: nothing lost); the fence lines stay as written and the block's Copy sits on its opening fence line, so it
// takes no room of its own. Used by Live's text rows (LiveRows.tsx) and the Prompt panel's feed (PromptFeed.tsx);
// `data-reply` marks the element a refused clipboard selects for the reply's own Copy.
import { useRef } from "react";
import { CopyButton } from "../../lib/ui";
import { segments, type Code } from "../../lib/copyText";

export const REPLY_TITLE = "Copy: this reply as the agent wrote it, onto the clipboard (nothing is written anywhere else)";
const CODE_TITLE = "Copy: this block's code only, its indentation kept, onto the clipboard (nothing is written anywhere else)";

function Block({ s }: { s: Code }) {
  const body = useRef<HTMLDivElement>(null);
  return (
    <div className="reply-code" data-testid="reply-code">
      <div className="reply-fence">
        <span>{s.open}</span>
        <CopyButton testid="copy-code" text={() => s.body} of={() => body.current} title={CODE_TITLE} />
      </div>
      <div className="reply-code-body" ref={body}>{s.body}</div>
      {s.close && <div className="reply-fence">{s.close}</div>}
    </div>
  );
}

/** One line break next to a block is the block's own edge: it is not drawn twice. */
function edge(t: string, before: boolean, after: boolean): string {
  const s = before ? t.replace(/^\r?\n/, "") : t;
  return after ? s.replace(/\r?\n$/, "") : s;
}

type Props = { text: string; className: string; testid: string; kind?: string; typing?: boolean };

export function ReplyText({ text, className, testid, kind, typing }: Props) {
  const segs = segments(text);
  return (
    <div className={className} data-testid={testid} data-kind={kind} data-typing={typing || undefined} data-reply="">
      {segs.map((s, i) => (s.code ? <Block key={i} s={s} /> : edge(s.text, i > 0, i < segs.length - 1)))}
    </div>
  );
}
