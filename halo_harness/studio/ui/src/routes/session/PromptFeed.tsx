// The Prompt panel's conversation (3.3.11.0 R1): the chosen session read the way the terminal reads it -- your
// turns (with the receipt's four marks: sent, delivered, read, replied; 3.6.0.2 P24: nothing marks which box a turn
// was typed in), the assistant's text, each tool call folded to one line (with the pack policy's line when one
// answered it), the asks with the TUI card's buttons (answered through the socket's `answer`; P23: an ask answered
// anywhere shows one line in their place), a steer's one row with the muted steering line (P22), `Interrupted.`
// under a turn stopped from anywhere (P20) and a slash command's output lines. It reads the stream the Live panel
// already keeps (shared/liveFeed.ts, the session's main agent) plus the turns and outputs of promptStore.ts.
// 3.6.0.11: a prompt typed before Studio attached (the backlog's `asked` line of main) is a turn too (promptRows.ts).
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useBorn } from "../../lib/motion/born";
import { CopyButton, Empty } from "../../lib/ui";
import { replySource } from "../../lib/copyText";
import { short } from "../orchestra/format";
import { keyOf } from "../fleet/store";
import { useLive, type LiveLine } from "../shared/liveFeed";
import { LADDER, STATE_WORDS, usePrompt, type Receipt } from "./promptStore";
import { feedRows } from "./promptRows";
import { answer, stopBang } from "./promptSend";
import { askLabel, BANG_STOP, BANG_STOP_TITLE, isBang, STEERING } from "./promptWords";
import { REPLY_TITLE, ReplyText } from "./ReplyText";

const MAX_ROWS = 240;

/** The receipt's four marks beside your turn; the state's word (and a failure's reason) in the title. 3.3.15.0 L1:
 *  a rung reached after the page drew climbs (`data-climb`, 160 ms after the one before, once: styles/motion.css). */
export function Marks({ r }: { r: Receipt | undefined }) {
  const at = r ? LADDER.indexOf(r.state) : -1;
  const [born] = useBorn();
  const [base, setBase] = useState(born ? -1 : at); // the rungs on before the page drew stay still
  const failed = r?.state === "failed";
  const title = !r ? "no receipt (typed in the terminal)" : `${STATE_WORDS[r.state] || r.state}${r.reason ? `: ${r.reason}` : ""}`;
  return (
    <span className="spp-marks" data-testid="prompt-receipt" data-state={r?.state || "none"} title={title} aria-label={title}>
      {LADDER.map((s, i) => {
        const climb = i <= at && i > base && !failed;
        return <i key={s} className="spp-mark" data-step={s} data-on={i <= at || undefined} data-failed={failed || undefined} data-climb={climb || undefined}
                  style={climb ? ({ "--climb": i - base - 1 } as CSSProperties) : undefined} onAnimationEnd={i === at ? () => setBase(at) : undefined} />;
      })}
    </span>
  );
}

type AskButton = { label: string; fields: Record<string, unknown> };

// A button's words are THE table's for its answer with no typed words (promptWords.ts askLabel); the buttons send what
// 3.6.0.1's sent.
const button = (kind: string, fields: Record<string, unknown>, sent = fields): AskButton => ({ label: askLabel(kind, fields), fields: sent });

function buttonsFor(kind: string, options: string[], draft: string): AskButton[] {
  const words = draft.trim();
  if (kind === "permission")
    return [button(kind, { action: "allow", scope: "once" }), button(kind, { action: "allow", scope: "session" }),
            button(kind, { action: "deny" }, { action: "deny", ...(words ? { message: words } : {}) })];
  if (kind === "question")
    return [...options.map((o) => button(kind, { answer: o })), ...(words ? [{ label: "Answer with what you typed", fields: { answer: words } }] : [])];
  if (kind === "plan") return [button(kind, { approved: true }), button(kind, { approved: false }, { approved: false, feedback: words })];
  return [button(kind, { action: "accept" }), button(kind, { action: "stop" })];
}

function Ask({ sid, l }: { sid: string; l: LiveLine }) {
  const id = l.id || "";
  const card = `${id}#${l.n}`; // a session may ask with the same id again: each card is its own
  const info = usePrompt((s) => s.asks[id]);
  const mine = usePrompt((s) => s.answered[card]);
  const heard = usePrompt((s) => s.heard[id]); // P23: `ask_answered`, from any side, after this card was asked
  const done = mine || (heard && heard.ts >= l.ts ? heard.line : "");
  const draft = usePrompt((s) => s.draft);
  const kind = info?.kind || l.ask || "permission";
  return (
    <div className="spp-ask" data-testid="prompt-ask" data-kind={kind} data-answered={done ? true : undefined}
      data-heard={heard ? true : undefined}>
      <div className="spp-ask-what">{l.text}</div>
      {done ? (
        <div className="mono muted" data-testid="prompt-ask-done">{done}</div>
      ) : (
        <div className="spp-ask-keys">
          {buttonsFor(kind, info?.options || [], draft).map((b) => (
            <button key={b.label} type="button" className="btn btn-default btn-sm" data-testid="prompt-ask-btn" data-label={b.label}
                    onClick={() => void answer(sid, kind, id, b.fields, card)} title={`${b.label}: answers this ${kind} card in the session`}>
              <span className="btn-label">{b.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LiveBody({ sid, l }: { sid: string; l: LiveLine }) {
  if (l.kind === "ask") return <Ask sid={sid} l={l} />;
  if (l.kind === "tool") {
    const row = (
      <div className="spp-tool mono" data-testid="prompt-tool" data-error={l.error || undefined} data-running={!l.ended || undefined}>
        <span className="spp-dot">⏺</span> {l.tool}{l.target ? ` ${short(l.target, 70)}` : ""}
        {l.result !== undefined && <span className="muted"> {l.error ? "✕" : "→"} {short(l.result, 110)}</span>}
        {l.policy && <div className="spp-policy" data-testid="prompt-tool-policy">{l.policy}</div>}
      </div>
    );
    if (l.ended || !isBang(l.id)) return row;
    return ( // 3.6.0.12 BS: a `!` command that still runs carries its own Stop (the session's interrupt)
      <div className="spp-bang">
        {row}
        <button type="button" className="btn btn-default btn-sm" data-testid="prompt-bang-stop" title={BANG_STOP_TITLE} onClick={() => void stopBang(sid)}>
          <span className="btn-label">{BANG_STOP}</span>
        </button>
      </div>
    );
  }
  if (l.kind === "you") return <div className="spp-steer" data-testid="prompt-steer-row"><span className="mono muted">↳ steer: </span>{short(l.text, 300)}</div>;
  if (l.kind === "state" || l.kind === "error") return <div className="spp-state mono" data-state={l.state || (l.kind === "error" ? "failed" : "")}>{short(l.text, 200)}</div>;
  return <Reply l={l} />;
}

/** 3.6.0.6 C: a reply, its code blocks each with a Copy, and its own Copy on the line under it (room from the first draw). */
function Reply({ l }: { l: LiveLine }) {
  const box = useRef<HTMLDivElement>(null);
  return (
    <div ref={box}>
      <ReplyText text={l.text} className="spp-text" testid="prompt-text" />
      <div className="spp-reply-foot">
        <CopyButton testid="copy-reply" text={() => replySource(l)} of={() => box.current?.querySelector("[data-reply]")} title={REPLY_TITLE} />
      </div>
    </div>
  );
}

export function PromptFeed({ sid, hid }: { sid: string; hid: string }) {
  const key = keyOf(hid, sid, "main");
  const lines = useLive((s) => s.lines);
  const turns = usePrompt((s) => s.turns);
  const outs = usePrompt((s) => s.outs);
  const receipts = usePrompt((s) => s.receipts);
  const box = useRef<HTMLDivElement>(null);
  const rows = useMemo(() => feedRows(turns, lines, outs, sid, key, MAX_ROWS), [turns, lines, outs, sid, key]); // promptRows.ts
  useEffect(() => {
    const el = box.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 120) el.scrollTop = el.scrollHeight;
  }, [rows]);
  if (!rows.length)
    return <Empty title="Type below" testid="prompt-empty" body="Your turns, the replies, each tool call on one line and the asks land here, as the terminal shows them. A line starting with / runs that command." />;
  return (
    <div className="spp-feed" ref={box} data-testid="prompt-feed">
      {rows.map((r) =>
        r.turn ? (
          <div key={"t" + r.turn.n} className="spp-row spp-you" data-testid="prompt-turn" data-ts={r.ts} data-via={r.turn.via || undefined} data-receipt={r.turn.receipt || undefined}
               data-steer={r.turn.steer || undefined}
               data-receipt-state={receipts[r.turn.receipt]?.state || undefined}>
            <span className="spp-you-mark mono">›</span>
            <span className="spp-you-text">{r.turn.text}</span>
            {r.turn.receipt && <Marks r={receipts[r.turn.receipt]} />}
            {r.turn.steer && <div className="spp-steering mono muted" data-testid="prompt-steering">{STEERING}</div>}
          </div>
        ) : r.out?.note ? (
          <div key={"o" + r.out.n} className="spp-row spp-note mono muted" data-testid="prompt-note">{r.out.lines.join("\n")}</div>
        ) : r.out ? (
          <div key={"o" + r.out.n} className="spp-row spp-out" data-testid="prompt-slash-out" data-error={r.out.error || undefined}>
            <div className="spp-out-cmd mono">{r.out.line}</div>
            <pre className="spp-out-lines mono" data-testid="prompt-slash-lines">{r.out.lines.join("\n")}</pre>
          </div>
        ) : (
          <div key={"l" + r.line!.n} className="spp-row" data-kind={r.line!.kind} data-testid="prompt-line" data-n={r.line!.n} data-ts={r.ts}>
            <LiveBody sid={sid} l={r.line!} />
          </div>
        ),
      )}
    </div>
  );
}
