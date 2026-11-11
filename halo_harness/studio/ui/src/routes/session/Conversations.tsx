// session-conversations (3.3.16.2, the owner: "a section that does this for model to model or agent to agent
// conversations"): an optional Session panel (the header's "+" adds it; never open on load). Its strip: how many
// threads and messages. Left, the pairs of agents that have talked, newest first (`main <-> researcher`, the count,
// the last line); right, the chosen pair's thread: each message a hairline bubble on its speaker's side in that
// agent's colour, its reason as a mono caps word, its time, a reply indented under what it answers. A bubble's click
// scrolls Live to its TALK row; "show in Live" narrows Live to the pair. The messages are liveTalk.ts `talks`.
import { useEffect, useMemo, useState } from "react";
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { clock, short } from "../orchestra/format";
import { hueOf } from "../shared/hues";
import { pairOf, useTalks, type TalkMsg } from "../shared/liveTalk";
import { startLiveTree } from "../shared/liveTree";
import { goRow } from "./LiveThink";
import { WHY_WORD } from "./LiveTalk";
import { sess } from "./store";
import { useConvPick } from "./convPick"; // 3.3.18.0: a click on a line of Agents -> Live opens its pair

type Pair = { id: string; a: string; b: string; aName: string; bName: string; msgs: TalkMsg[]; last: TalkMsg };

function pairsOf(msgs: TalkMsg[]): Pair[] {
  const by = new Map<string, Pair>();
  for (const m of msgs) {
    const id = pairOf(m);
    const p = by.get(id);
    if (p) (p.msgs.push(m), (p.last = m));
    else by.set(id, { id, a: m.fromKey, b: m.toKey || "machine:" + (m.machine || "?"), aName: m.fromName, bName: m.toName, msgs: [m], last: m });
  }
  return [...by.values()].sort((x, y) => y.last.ts - x.last.ts || y.last.n - x.last.n);
}

const EMPTY = "No agent has spoken to another yet: when main hands a task to an agent, it shows here.";

/** Live shows row `n`: the filters that hide it are cleared first. */
function showRow(n: number): void {
  if (!document.querySelector(`[data-testid="session-live-scroll"] [data-n="${n}"]`)) sess.update(() => ({ pin: "", kind: "", think: false, pair: "" }));
  sess.update(() => ({ follow: false }));
  window.setTimeout(() => goRow(n), 30);
}

function Bubble({ m, left, nested }: { m: TalkMsg; left: boolean; nested: boolean }) {
  return (
    <button type="button" className="conv-bubble" data-testid="conv-bubble" data-side={left ? "left" : "right"} data-nested={nested || undefined} data-n={m.n}
            data-hc={hueOf(m.fromKey)} onClick={() => showRow(m.n)} title="Show it in Live">
      <span className="conv-meta mono">
        <span className="conv-who">{m.fromName}</span>
        <span className="conv-why">{WHY_WORD[m.why] || m.why.toUpperCase()}{m.square ? ` · ${m.square}` : ""}</span>
        <span className="conv-time">{clock(m.ts)}</span>
      </span>
      <span className="conv-text">{short(m.text, 600)}</span>
    </button>
  );
}

function Thread({ p }: { p: Pair }) {
  const ids = new Set(p.msgs.map((m) => m.id));
  return (
    <div className="conv-thread" data-testid="conv-thread">
      <div className="conv-thread-head">
        <span className="rail-label mono">{short(p.aName, 18)} ↔ {short(p.bName, 18)}</span>
        <button type="button" className="og-link mono" data-testid="conv-show-live" onClick={() => sess.update(() => ({ pair: p.id, kind: "", think: false, pin: "", follow: true }))}>
          show in Live
        </button>
      </div>
      {p.msgs.map((m) => <Bubble key={m.id + m.n} m={m} left={m.fromKey === p.a} nested={!!m.re && ids.has(m.re)} />)}
    </div>
  );
}

export function ConversationsDetail() {
  useEffect(() => startLiveTree(), []);
  const msgs = useTalks((s) => s.msgs);
  const pairs = useMemo(() => pairsOf(msgs), [msgs]);
  const [chosen, setChosen] = useState("");
  const asked = useConvPick();
  useEffect(() => void (asked.pair && setChosen(asked.pair)), [asked.n]); // eslint-disable-line react-hooks/exhaustive-deps
  const cur = pairs.find((p) => p.id === chosen) || pairs[0];
  if (!pairs.length) return <div className="conv-wrap" data-testid="conv-panel"><Empty title="No conversation yet" body={EMPTY} testid="conv-empty" /></div>;
  return (
    <div className="conv-wrap" data-testid="conv-panel"><div className="conv">
      <div className="conv-pairs" role="listbox" aria-label="Pairs of agents">
        {pairs.map((p) => (
          <button key={p.id} type="button" role="option" aria-selected={p === cur} className="conv-pair" data-testid="conv-pair" data-on={p === cur || undefined} onClick={() => setChosen(p.id)}>
            <span className="conv-pair-names mono">{short(p.aName, 16)} ↔ {short(p.bName, 16)}</span>
            <span className="conv-pair-count mono muted">{p.msgs.length}</span>
            <span className="conv-pair-last muted">{short(p.last.text.replace(/\s+/g, " "), 90)}</span>
          </button>
        ))}
      </div>
      {cur && <Thread p={cur} />}
    </div></div>
  );
}

export function ConversationsGlance() {
  useEffect(() => startLiveTree(), []);
  const msgs = useTalks((s) => s.msgs);
  const threads = useMemo(() => new Set(msgs.map(pairOf)).size, [msgs]);
  const last = msgs[msgs.length - 1];
  return (
    <div className="glance" data-testid="conv-glance">
      <div className="glance-hint mono" data-testid="conv-counts">{threads} thread{threads === 1 ? "" : "s"} · {msgs.length} message{msgs.length === 1 ? "" : "s"}</div>
      {last && <div className="glance-hint">{short(`${last.fromName} → ${last.toName}: ${last.text}`, 90)}</div>}
    </div>
  );
}

export function useConversationsMotion(): MotionState {
  const n = useTalks((s) => s.msgs.length);
  return n ? "idle" : "none";
}
