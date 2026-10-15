// fleet-attention: ONE queue of every decision that waits on you, across
// the fleet (permission, question, plan and approval cards, fleet asks,
// waiting and paused agents, flow and Orchestra gates, commands a member's
// owner has to allow, spend caps, file conflicts), oldest first. Each row:
// who (harness, session, agent), what, how long it has waited, and its
// one-key answers: A accept / allow, R deny or redo with a text, S stop, O
// open the panel it belongs to. J / K (or the arrows) move between rows
// while the panel has the focus. Answers go through the route that already
// handles each kind (studio/fleet_answer.py); the count is live from the feed.
import { useEffect, useRef, useState } from "react";
import { Button, Empty, Kbd } from "../../lib/ui";
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { short } from "../orchestra/format";
import { answerRow } from "./extras";
import { age, panels, usePanels, type AttnRow } from "./pstore";
import { useNow } from "./store";

const ORDER = ["a", "r", "s", "o"];
const KIND: Record<string, string> = {
  permission: "permission", question: "question", plan: "plan", approval: "approval", fleet_ask: "fleet ask", waiting: "waiting",
  paused: "paused", flow_gate: "flow gate", orchestra_gate: "orchestra gate", control_ask: "command", cap: "spend cap", conflict: "conflict",
};

/** A key on a row: R with a text first opens the reply box. */
function press(row: AttnRow, key: string): void {
  if (!row.keys[key]) return;
  if (key === "r" && row.text_for === "r") panels.update(() => ({ replyFor: row.id, attnSel: row.id }));
  else void answerRow(row, key);
}

function Reply({ row }: { row: AttnRow }) {
  const [text, setText] = useState("");
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => box.current?.focus(), []);
  const needs = row.kind !== "permission";
  const send = () => (needs && !text.trim() ? undefined : void answerRow(row, "r", text.trim()));
  return (
    <div className="fat-reply">
      <input ref={box} className="input" value={text} onChange={(e) => setText(e.target.value)} data-testid="fleet-attn-text"
             placeholder={row.kind === "permission" ? "why not (optional); Enter denies" : `${row.keys.r}: type it, Enter sends`}
             onKeyDown={(e) => {
               if (e.key === "Enter") (e.preventDefault(), send());
               else if (e.key === "Escape") (e.preventDefault(), e.stopPropagation(), panels.update(() => ({ replyFor: "" })));
             }} />
      <Button size="sm" variant="primary" disabled={needs && !text.trim()} onClick={send} data-testid="fleet-attn-send">{row.keys.r}</Button>
      <Button size="sm" variant="ghost" onClick={() => panels.update(() => ({ replyFor: "" }))}>Cancel</Button>
    </div>
  );
}

function Row({ row, sel, now }: { row: AttnRow; sel: boolean; now: number }) {
  const replying = usePanels((s) => s.replyFor === row.id);
  return (
    <li className="fat-row" data-testid="fleet-attn-row" data-kind={row.kind} data-id={row.id} aria-selected={sel} onClick={() => panels.update(() => ({ attnSel: row.id }))}>
      <div className="fat-top">
        <span className="og-chip mono fat-kind" data-kind={row.kind}>{KIND[row.kind] || row.kind}</span>
        <span className="fat-who mono" title={`${row.harness_name} · ${row.session} · ${row.agent}`}>
          {row.harness_name}{row.session ? ` · ${short(row.session, 26)}` : ""}{row.agent ? ` · ${row.agent}` : ""}
        </span>
        <span className="spacer" />
        <span className="fat-age mono" title="how long it has waited">{age(row.since, now)}</span>
      </div>
      <div className="fat-what">{row.what}</div>
      {row.detail && <div className="fat-detail muted">{short(row.detail, 200)}</div>}
      <div className="fat-keys">
        {ORDER.filter((k) => row.keys[k]).map((k) => (
          <button key={k} className="fat-key" data-key={k} data-testid="fleet-attn-key" onClick={(e) => (e.stopPropagation(), press(row, k))}>
            <Kbd keys={k.toUpperCase()} /> {row.keys[k]}
          </button>
        ))}
        {row.remote_attached > 0 && <span className="muted fat-phone" title="a phone is attached to this session">phone attached</span>}
      </div>
      {replying && <Reply row={row} />}
    </li>
  );
}

/** A / R / S / O and J / K while the focus is in this panel (capture: before the hop keys). */
function useAttentionKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (!t?.closest?.('[data-panel="fleet-attention"]') || t.closest("input, textarea, select")) return;
      const s = panels.get();
      const i = s.attention.findIndex((r) => r.id === s.attnSel);
      const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (k === "j" || k === "ArrowDown" || k === "k" || k === "ArrowUp") {
        const n = s.attention.length;
        if (!n) return;
        const d = k === "j" || k === "ArrowDown" ? 1 : -1;
        panels.update(() => ({ attnSel: s.attention[i < 0 ? 0 : (i + d + n) % n].id }));
      } else if (ORDER.includes(k) && i >= 0 && s.attention[i].keys[k]) press(s.attention[i], k);
      else return;
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);
}

export function AttentionDetail() {
  const rows = usePanels((s) => s.attention);
  const sel = usePanels((s) => s.attnSel);
  const loaded = usePanels((s) => s.attnLoaded);
  const error = usePanels((s) => s.attnError);
  const now = useNow(rows.length > 0, 5000);
  useAttentionKeys();
  if (!loaded) return <div className="og-wait mono muted">reading what waits on you...</div>;
  if (error && !rows.length) return <Empty title="Studio could not read the queue" body={error} />;
  if (!rows.length)
    return <Empty title="Nothing waits on you" body="A card, a gate, a paused agent, a spend cap or two agents on one file shows here the moment it needs you, from every harness." testid="fleet-attn-empty" />;
  return (
    <div className="fat" data-testid="fleet-attention-list">
      <div className="fat-head mono muted">
        {rows.length} waiting · oldest first · <Kbd keys="J" /> <Kbd keys="K" /> move, <Kbd keys="A" /> <Kbd keys="R" /> <Kbd keys="S" /> <Kbd keys="O" /> answer
      </div>
      <ul className="fat-list">
        {rows.map((r) => <Row key={r.id} row={r} sel={r.id === sel} now={now} />)}
      </ul>
    </div>
  );
}

export function AttentionGlance() {
  const count = usePanels((s) => s.attnCount ?? s.attention.length);
  const first = usePanels((s) => s.attention[0]);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={count} label="need you" tone={count ? "warn" : undefined} />
      </div>
      <div className="glance-hint">{first ? `${first.harness_name}: ${short(first.what, 60)}` : "Nothing waits on you."}</div>
    </div>
  );
}

export function useAttentionMotion(): MotionState {
  const count = usePanels((s) => s.attnCount ?? s.attention.length);
  return count ? "waiting" : "idle";
}
