// The Steward page's chat box (3.3.7.0 R5; ollama_steward/chat.py): a conversation with the steward's own small model
// over the host's findings, the reservations and the adviser's numbers. It answers in plain words, may read the card,
// the ledger, the events, the profiles, the speed cards, the knowledge; may land one Halo-side change citing a
// finding; may leave a button for what costs more (retire, download and verify, a bench, the battery). Each answer
// carries its cost ("local, 4 s" or the dollars). "Ask a bigger model" says what it costs first, then sends the same
// context once to the session's main model. `halo ollama steward chat "<question>"` is the same from a terminal.
// 3.3.15.0 R3: the question box is the one TextBox (three lines, grows with the question); Enter asks, Shift+Enter is
// a new line.
import { useEffect, useState } from "react";
import { Button, TextBox } from "../../lib/ui";
import { ask, chat, loadBiggerCost, loadChat, press, useChat, type ChatRow } from "./chatstore";

function Row({ r }: { r: ChatRow }) {
  const said = useChat((s) => s.said[r.id]);
  if (r.role === "user") return <li className="lc-chat-q" data-testid="steward-chat-q">{r.text}</li>;
  if (r.role === "tool") {
    return (
      <li className="lc-chat-tool mono muted" data-testid="steward-chat-tool" data-ok={r.ok || undefined}>
        [{r.tool}] {(r.text || "").split("\n")[0]}
      </li>
    );
  }
  if (r.role === "button" && r.action) {
    const b = r.action;
    return (
      <li className="lc-chat-button" data-testid="steward-chat-button" data-verb={b.verb}>
        <span className="muted">{r.text}</span>
        <span className="lc-model-acts">
          {!said?.ok && <Button size="sm" variant="primary" onClick={() => void press(b, r.id)} title={b.cli}
                                data-testid="steward-chat-press">{b.label}</Button>}
          <code className="mono lc-cli-line" title="the same from a terminal">{b.cli}</code>
        </span>
        {said && <span className="mono lc-said" data-ok={said.ok || undefined}>{said.text}</span>}
      </li>
    );
  }
  return (
    <li className="lc-chat-a" data-testid="steward-chat-a" data-role={r.role}>
      <div className="lc-chat-text">{r.text}</div>
      <span className="og-chip mono" data-testid="steward-chat-cost" title={r.model || ""}>
        {r.role === "bigger" ? "main model · " : ""}{r.cost || "no cost"}
      </span>
    </li>
  );
}

export function StewardChat() {
  const rows = useChat((s) => s.rows);
  const model = useChat((s) => s.model);
  const why = useChat((s) => s.why);
  const busy = useChat((s) => s.busy);
  const error = useChat((s) => s.error);
  const bigger = useChat((s) => s.bigger);
  const [q, setQ] = useState("");
  const [asking, setAsking] = useState(false);
  useEffect(() => {
    void loadChat();
  }, []);
  const send = (big: boolean) => {
    const text = q;
    setQ("");
    setAsking(false);
    chat.update(() => ({ bigger: "" }));
    void ask(text, big);
  };
  return (
    <section className="lc-block lc-chat" aria-label="Talk to the steward" data-testid="steward-chat">
      <div className="rail-label mono">TALK TO THE STEWARD · {model || "no model"}</div>
      <p className="mono muted lc-status" data-testid="steward-chat-model">{model ? `${model}: ${why}` : why}</p>
      <ul className="lc-chat-rows" data-testid="steward-chat-rows">
        {(rows || []).slice(-40).map((r) => <Row key={r.id} r={r} />)}
      </ul>
      {busy && <p className="mono muted" data-testid="steward-chat-busy">the steward is answering...</p>}
      {error && <p className="lc-foreign" data-testid="steward-chat-error">{error}</p>}
      <form className="lc-chat-form" onSubmit={(e) => {
        e.preventDefault();
        send(false);
      }}>
        <TextBox className="lc-chat-input" value={q} onChange={(e) => setQ(e.target.value)} disabled={busy}
                 placeholder="Ask, e.g. why is the card busy? Can the 27B fit?" data-testid="steward-chat-input"
                 onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), q.trim() && model && send(false))} />
        <Button size="sm" variant="primary" disabled={busy || !q.trim() || !model} data-testid="steward-chat-ask"
                onClick={() => send(false)}>Ask</Button>
        <Button size="sm" variant="ghost" disabled={busy || !q.trim()} data-testid="steward-chat-bigger"
                onClick={() => {
                  setAsking(true);
                  void loadBiggerCost(q);
                }} title="the same context, once, to the session's main model: its cost is said first">Ask a bigger model...</Button>
      </form>
      {asking && (
        <div className="lc-chat-bigger mono" data-testid="steward-chat-bigger-cost">
          <span>{bigger || "reading the cost..."}</span>
          <Button size="sm" disabled={!bigger || busy} onClick={() => send(true)} data-testid="steward-chat-bigger-yes">Ask it</Button>
          <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
        </div>
      )}
    </section>
  );
}
