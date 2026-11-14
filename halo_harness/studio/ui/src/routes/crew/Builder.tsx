// The builder box (3.6.0.0 R1; the design's "The builder (one box, every tab)"): docked at the foot of the tab, one
// line tall; its conversation opens above it only after a request (never by itself on load). A reply that would change
// something comes as a preview: one line per change, each with a tick; a line that lets an agent do more (a tool beyond
// reading, a less careful mode, a higher money cap, the web) is amber and never ticked for you. Apply writes the ticked
// lines, a receipt offers Undo; Discard drops them. The line beside the box: its model, what a request costs, and the
// day's spend against its cap. 3.6.0.0 R2: one box per tab (`tab`), each its own conversation; on Workflows an agent
// the request needs and you do not have comes as a proposal card with "make it" (the agent form, filled, then back).
import { useEffect, useRef } from "react";
import { Button } from "../../lib/ui";
import { apply, discardPreview, loadMeta, send, setText, tick, toggleOpen, undo, useBuilder, type Tab } from "./builderStore";
import { makeIt } from "./flows/makeIt";
import { useFlows } from "./flows/flowStore";
import { useCrew } from "./store";
import type { Change, Msg } from "./types";

function Line({ c, tab }: { c: Change; tab: Tab }) {
  return (
    <label className="cw-pv-line" data-widen={c.widen || undefined} data-testid="builder-line" data-kind={c.kind} data-target={c.target}>
      <input type="checkbox" checked={c.ticked} onChange={(e) => tick(c.id, e.target.checked, tab)} data-testid="builder-tick" data-widen={c.widen ? "1" : "0"} />
      <span>{c.summary}{c.widen && <b className="cw-widen"> (lets it do more: not ticked for you)</b>}</span>
    </label>
  );
}

function Card({ c }: { c: Change }) {
  const a = c.body!;
  const uses = a.uses?.length ? a.uses.join(", ") : "nothing";
  return (
    <div className="cw-card" data-testid="builder-card" data-name={a.name}>
      <span className="cw-line"><b>New agent: {a.name}</b> · {a.does} · {a.model} · may use: {uses}</span>
      <Button onClick={() => makeIt(c)} data-testid="builder-make-it" title="Open the agent form filled in with it; Save it there, and you come back here">make it</Button>
    </div>
  );
}

function Preview({ tab }: { tab: Tab }) {
  const pending = useBuilder((s) => s.pending, tab);
  const cost = useBuilder((s) => s.msgs[s.msgs.length - 1]?.cost, tab);
  if (!pending.length) return null;
  const cards = tab === "workflows" ? pending.filter((c) => c.kind === "create" && c.body && c.target.startsWith("agent:")) : [];
  return (
    <div className="cw-pv" data-testid="builder-preview">
      <div className="cw-row"><b>It will do this</b><span className="cw-line">untick what you do not want; nothing is written until Apply</span></div>
      {cards.map((c) => <Card key={c.id} c={c} />)}
      {pending.map((c) => <Line key={c.id} c={c} tab={tab} />)}
      <div className="cw-row">
        <Button variant="primary" onClick={() => void apply(tab)} data-testid="builder-apply">Apply</Button>
        <Button onClick={() => discardPreview(tab)} data-testid="builder-discard">Discard</Button>
        {typeof cost === "number" && <span className="cw-line">this reply cost ${cost.toFixed(4)}</span>}
      </div>
    </div>
  );
}

function Message({ m, last, tab }: { m: Msg; last: boolean; tab: Tab }) {
  return (
    <div className="cw-msg" data-me={m.me || undefined} data-testid="builder-msg">
      <span className="cw-msg-who mono">{m.me ? "you" : "builder"}</span>
      <div className="cw-msg-text">{m.text}</div>
      {m.question && (
        <div className="cw-row" data-testid="builder-question">
          {m.question.text && <span className="cw-line">{m.question.text}</span>}
          {m.question.choices.map((ch, i) => (
            <Button key={ch} variant={i === 0 ? "primary" : "default"} disabled={!last} onClick={() => void send(ch, tab)} data-testid="builder-choice">{ch}</Button>
          ))}
        </div>
      )}
    </div>
  );
}

function Conversation({ tab }: { tab: Tab }) {
  const msgs = useBuilder((s) => s.msgs, tab);
  const open = useBuilder((s) => s.open, tab);
  const sending = useBuilder((s) => s.sending, tab);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [msgs.length, open, sending]);
  if (!open || !msgs.length) return null;
  return (
    <div className="cw-conv" ref={box} data-testid="builder-conversation">
      {msgs.map((m, i) => <Message key={i} m={m} last={i === msgs.length - 1} tab={tab} />)}
      {sending && <div className="cw-line" data-testid="builder-sending">The builder is working on it...</div>}
      <Preview tab={tab} />
    </div>
  );
}

function MetaLine({ tab }: { tab: Tab }) {
  const m = useBuilder((s) => s.meta, tab);
  if (!m) return <span className="cw-line">reading the builder's model...</span>;
  return (
    <span className="cw-line cw-meta mono" data-testid="builder-meta" data-reached={m.reached || undefined} title={`Its model is ${m.model_from}; the cap is studio.builder.cap_usd`}>
      {m.model || "no model"} · {m.typical} · <b>${m.spent_usd.toFixed(3)}</b> of ${m.cap_usd.toFixed(2)} today
    </span>
  );
}

export function BuilderBox({ tab = "agents" }: { tab?: Tab }) {
  const text = useBuilder((s) => s.text, tab);
  const sending = useBuilder((s) => s.sending, tab);
  const open = useBuilder((s) => s.open, tab);
  const n = useBuilder((s) => s.msgs.length, tab);
  const receipt = useBuilder((s) => s.receipt, tab);
  const agent = useCrew((s) => s.form?.name || "");
  const flow = useFlows((s) => s.form?.name || "");
  useEffect(() => void loadMeta(tab), [tab]);
  const hint = tab === "workflows" ? `Describe a workflow, or say what to change about ${flow || "the open one"}`
    : `Describe an agent, or say what to change about ${agent || "the open one"}`;
  return (
    <section className="cw-bld" aria-label="The builder" data-testid="builder" data-builder-tab={tab}>
      <Conversation tab={tab} />
      {receipt && (
        <div className="cw-receipt" data-testid="builder-receipt">
          <span className="cw-line">{receipt.line}</span>
          <Button onClick={() => void undo(tab)} data-testid="builder-undo">Undo</Button>
        </div>
      )}
      <div className="cw-bld-in">
        <b className="mono cw-bld-name">BUILDER</b>
        <input className="input cw-bld-input" value={text} placeholder={hint} title={hint} aria-label="Ask the builder" data-testid="builder-input"
               onChange={(e) => setText(e.target.value, tab)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(undefined, tab); } }} />
        <Button variant="primary" disabled={!text.trim() || sending} onClick={() => void send(undefined, tab)} data-testid="builder-send">Send</Button>
        {n > 0 && <Button onClick={() => toggleOpen(tab)} aria-expanded={open} data-testid="builder-toggle">{open ? "Hide the conversation" : `Conversation (${n})`}</Button>}
        <MetaLine tab={tab} />
      </div>
    </section>
  );
}

export const AgentsBuilder = () => <BuilderBox tab="agents" />;
export const FlowsBuilder = () => <BuilderBox tab="workflows" />;
