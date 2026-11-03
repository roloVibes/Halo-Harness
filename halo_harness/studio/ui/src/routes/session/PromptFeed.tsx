// The Prompt panel's conversation (3.3.11.0 R1): the chosen session read the way the terminal reads it -- your
// turns (with "from Studio" when this page sent them, and the receipt's four marks: sent, delivered, read,
// replied), the assistant's text, each tool call folded to one line (with the pack policy's line when one
// answered it), the asks with the TUI card's buttons (answered through the socket's `answer`), the turn's end
// line and a slash command's output lines. It reads the stream the Live panel already keeps (shared/liveFeed.ts,
// the session's main agent) plus the turns and outputs of promptStore.ts; Live stays the stream for steering.
import { useEffect, useMemo, useRef } from "react";
import { Empty } from "../../lib/ui";
import { short } from "../orchestra/format";
import { keyOf } from "../fleet/store";
import { useLive, type LiveLine } from "../shared/liveFeed";
import { LADDER, STATE_WORDS, usePrompt, type Out, type Receipt, type Turn } from "./promptStore";
import { answer } from "./promptSend";

type Row = { ts: number; n: number; turn?: Turn; line?: LiveLine; out?: Out };
const SHOWN: LiveLine["kind"][] = ["text", "tool", "ask", "state", "error", "output", "you"];
const MAX_ROWS = 240;

/** The receipt's four marks beside your turn; the state's word (and a failure's reason) in the title. */
export function Marks({ r }: { r: Receipt | undefined }) {
  const at = r ? LADDER.indexOf(r.state) : -1;
  const failed = r?.state === "failed";
  const title = !r ? "no receipt (typed in the terminal)" : `${STATE_WORDS[r.state] || r.state}${r.reason ? `: ${r.reason}` : ""}`;
  return (
    <span className="spp-marks" data-testid="prompt-receipt" data-state={r?.state || "none"} title={title} aria-label={title}>
      {LADDER.map((s, i) => <i key={s} className="spp-mark" data-step={s} data-on={i <= at || undefined} data-failed={failed || undefined} />)}
    </span>
  );
}

type AskButton = { label: string; fields: Record<string, unknown> };

function buttonsFor(kind: string, options: string[], draft: string): AskButton[] {
  if (kind === "permission")
    return [{ label: "Allow", fields: { action: "allow", scope: "once" } }, { label: "Allow for this session", fields: { action: "allow", scope: "session" } },
            { label: "Deny", fields: { action: "deny", ...(draft.trim() ? { message: draft.trim() } : {}) } }];
  if (kind === "question")
    return [...options.map((o) => ({ label: o, fields: { answer: o } })), ...(draft.trim() ? [{ label: "Answer with what you typed", fields: { answer: draft.trim() } }] : [])];
  if (kind === "plan")
    return [{ label: "Approve the plan", fields: { approved: true } }, { label: "Keep planning", fields: { approved: false, feedback: draft.trim() } }];
  return [{ label: "Accept", fields: { action: "accept" } }, { label: "Stop", fields: { action: "stop" } }];
}

function Ask({ sid, l }: { sid: string; l: LiveLine }) {
  const id = l.id || "";
  const card = `${id}#${l.n}`; // a session may ask with the same id again: each card is its own
  const info = usePrompt((s) => s.asks[id]);
  const done = usePrompt((s) => s.answered[card]);
  const draft = usePrompt((s) => s.draft);
  const kind = info?.kind || l.ask || "permission";
  return (
    <div className="spp-ask" data-testid="prompt-ask" data-kind={kind} data-answered={done ? true : undefined}>
      <div className="spp-ask-what">{l.text}</div>
      {done ? (
        <div className="mono muted" data-testid="prompt-ask-done">answered: {done}</div>
      ) : (
        <div className="spp-ask-keys">
          {buttonsFor(kind, info?.options || [], draft).map((b) => (
            <button key={b.label} type="button" className="btn btn-default btn-sm" data-testid="prompt-ask-btn" data-label={b.label}
                    onClick={() => void answer(sid, kind, id, b.label, b.fields, card)} title={`${b.label}: answers this ${kind} card in the session`}>
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
  if (l.kind === "tool")
    return (
      <div className="spp-tool mono" data-testid="prompt-tool" data-error={l.error || undefined} data-running={!l.ended || undefined}>
        <span className="spp-dot">⏺</span> {l.tool}{l.target ? ` ${short(l.target, 70)}` : ""}
        {l.result !== undefined && <span className="muted"> {l.error ? "✕" : "→"} {short(l.result, 110)}</span>}
        {l.policy && <div className="spp-policy" data-testid="prompt-tool-policy">{l.policy}</div>}
      </div>
    );
  if (l.kind === "you") return <div className="spp-steer" data-testid="prompt-steer-row"><span className="mono muted">↳ steer: </span>{short(l.text, 300)}</div>;
  if (l.kind === "state" || l.kind === "error") return <div className="spp-state mono" data-state={l.state || (l.kind === "error" ? "failed" : "")}>{short(l.text, 200)}</div>;
  return <div className="spp-text" data-testid="prompt-text">{l.text}</div>;
}

export function PromptFeed({ sid, hid }: { sid: string; hid: string }) {
  const key = keyOf(hid, sid, "main");
  const lines = useLive((s) => s.lines);
  const turns = usePrompt((s) => s.turns);
  const outs = usePrompt((s) => s.outs);
  const receipts = usePrompt((s) => s.receipts);
  const box = useRef<HTMLDivElement>(null);
  const rows = useMemo(() => {
    const out: Row[] = [
      ...turns.filter((t) => t.sid === sid).map((t) => ({ ts: t.ts, n: t.n, turn: t })),
      ...lines.filter((l) => l.key === key && SHOWN.includes(l.kind)).map((l) => ({ ts: l.ts, n: l.n, line: l })),
      ...outs.filter((o) => o.sid === sid).map((o) => ({ ts: o.ts, n: o.n, out: o })),
    ];
    out.sort((a, b) => a.ts - b.ts || a.n - b.n);
    return out.slice(-MAX_ROWS);
  }, [turns, lines, outs, sid, key]);
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
               data-receipt-state={receipts[r.turn.receipt]?.state || undefined}>
            <span className="spp-you-mark mono">›</span>
            <span className="spp-you-text">{r.turn.text}</span>
            {r.turn.via === "studio" && <span className="spp-via mono" data-testid="prompt-via">from Studio</span>}
            {r.turn.receipt && <Marks r={receipts[r.turn.receipt]} />}
          </div>
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
