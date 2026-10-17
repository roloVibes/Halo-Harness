// design-thread (3.0.7.0 R3): the open project's turns as one thread, oldest
// first (ThreadParts.tsx: what you asked, the model's reply as safe
// markdown, what it cost and changed), the running turn at the bottom as it
// streams, and the Send box: Enter sends, Shift+Enter is a new line; while a
// turn runs the box offers Cancel turn. Send comments turns the open pins
// into one turn. The thread follows the newest line unless you scrolled up.
import { useEffect, useLayoutEffect, useRef } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { cancelTurn, send, sendComments } from "./actions";
import { design, live, money, spent, useDesign } from "./store";
import { HistoryTurn, LiveTurnView } from "./ThreadParts";

const SUGGESTIONS = [
  "A landing page hero for a developer tool: a bold headline, one sentence, two buttons and a product screenshot area.",
  "A pricing section with three tiers, the middle one highlighted, using the design system's colours.",
  "A mobile onboarding flow of three screens as one prototype, with knobs for spacing and the accent colour.",
];

function SendBox() {
  const draft = useDesign((s) => s.draft);
  const running = useDesign(live);
  const busy = useDesign((s) => s.busy);
  const focus = useDesign((s) => s.focusSend);
  const pins = useDesign((s) => (s.data?.comments || []).filter((c) => !c.resolved).length);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (focus) box.current?.focus();
  }, [focus]);
  const go = () => void send();
  return (
    <div className="dt-send">
      <textarea ref={box} className="input dt-input" rows={3} value={draft} data-testid="design-send-box"
                onChange={(e) => design.update(() => ({ draft: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    go();
                  }
                }}
                placeholder={running ? "A turn runs: write the next message meanwhile" : "Describe what to make or change. Enter sends, Shift+Enter adds a line."}
                aria-label="Message to the design model" />
      <div className="dt-send-row">
        {pins > 0 && <Button size="sm" variant="ghost" disabled={running} onClick={() => void sendComments()}>Send comments ({pins})</Button>}
        <span className="spacer" />
        {running ? (
          <Button size="sm" variant="danger" disabled={busy === "cancel"} onClick={() => void cancelTurn()} data-testid="design-cancel">Cancel turn</Button>
        ) : (
          <Button size="sm" variant="primary" kbd="Enter" disabled={!draft.trim() || busy === "send"} onClick={go} data-testid="design-send">Send</Button>
        )}
      </div>
    </div>
  );
}

export function ThreadDetail() {
  const data = useDesign((s) => s.data);
  const turn = useDesign((s) => s.turn);
  const loading = useDesign((s) => s.loading);
  const list = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const history = data?.history || [];
  const events = turn?.events.length || 0;
  useLayoutEffect(() => {
    const el = list.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [history.length, events, turn?.done]);
  if (!data) return loading ? <div className="og-wait mono muted">opening the project...</div> : <Empty title="No project open" body="Pick one in Projects, or make a new one." />;
  return (
    <div className="dt" data-testid="design-thread-list">
      <div className="dt-head mono muted">
        {data.meta.name} · {history.length} turn{history.length === 1 ? "" : "s"} · {money(spent(history))} · model {data.meta.model || "(default)"}
      </div>
      <div className="dt-list" ref={list} onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 24;
      }}>
        {history.map((h, i) => <HistoryTurn key={(h.ts || "") + i} h={h} n={i + 1} />)}
        {turn && <LiveTurnView t={turn} />}
        {!history.length && !turn && (
          <div className="dt-try">
            <p className="muted">Nothing asked yet. Start from one of these, or write your own below:</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="dt-sugg" onClick={() => design.update((x) => ({ draft: s, focusSend: x.focusSend + 1 }))}>{s}</button>
            ))}
          </div>
        )}
      </div>
      <SendBox />
    </div>
  );
}

export function ThreadGlance() {
  const n = useDesign((s) => s.data?.history.length || 0);
  const cost = useDesign((s) => spent(s.data?.history || []));
  const running = useDesign(live);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={n} label="turns" />
        <Metric value={money(cost)} label="spent" />
        <Metric value={running ? "yes" : "no"} label="running" tone={running ? "accent" : undefined} />
      </div>
      <div className="glance-hint">Expand for the thread and the message box.</div>
    </div>
  );
}

export function useThreadMotion(): MotionState {
  const running = useDesign(live);
  const failed = useDesign((s) => !!s.turn?.done && !!s.turn.result?.code && !s.turn.result.cancelled);
  const any = useDesign((s) => !!s.data);
  if (failed) return "error";
  return running ? "working" : any ? "idle" : "none";
}
