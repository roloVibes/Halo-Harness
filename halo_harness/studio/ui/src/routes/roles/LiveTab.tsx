// The Inspector's Live tab on the Roles canvas (3.0.7.0 R2; live-tab.js in
// the framed page before). For the selected card: a chip per agent when
// several run on it, then the one you watch -- state, harness, session,
// model, cost, what it was asked, its three streams (Thinking: its text as it
// types it; Working: one row per tool call with its result; Output: its
// hand-back), Pause / Resume, Stop (asks first), Follow, Pin and the Steer
// box. With nobody on the card: its track record, the last runs under its
// role (`GET fleet/history`), each with "replay" (the canvas plays that
// session back, Replay.tsx). Keys: J / K hop, Space pins, P pauses, F follows.
// 3.1.4.0 R2: while the agent is live on this harness its header has Watch
// in Session (the Session dashboard on its session, the agent selected).
import { useEffect, useRef } from "react";
import { useLocalAgent, WatchInSession } from "../session/Watch";
import { api } from "../../lib/api";
import { Button, Icon } from "../../lib/ui";
import { cost, short } from "../orchestra/format";
import { askStop, pin, toggleFollow, togglePause } from "../fleet/actions";
import { openReplay } from "../fleet/replay";
import { Steer } from "../fleet/Steer";
import { EMPTY } from "../fleet/streams";
import { OutputView, ThinkingView, WorkingView } from "../fleet/StreamViews";
import { useFleet } from "../fleet/store";
import { isLiveAgent, useByNode, watchAgent } from "./live";
import { nodeById, roles, useRoles, type LiveSub } from "./store";
import type { HistoryRun, LiveAgent } from "./types";

const ago = (ts?: number) => {
  const s = Math.max(0, Date.now() / 1000 - (Number(ts) || 0));
  return s < 60 ? `${Math.round(s)}s` : s < 3600 ? `${Math.round(s / 60)}m` : `${Math.round(s / 3600)}h`;
};

function History({ card, role, bio }: { card: string; role: string; bio: string }) {
  const h = useRoles((s) => s.history);
  useEffect(() => {
    roles.update(() => ({ history: { card, runs: null, error: "" } }));
    api.get<{ runs: HistoryRun[] }>("fleet/history", { role, bio, n: 12 })
      .then((r) => roles.get().history.card === card && roles.update(() => ({ history: { card, runs: r.runs || [], error: "" } })))
      .catch((e) => roles.get().history.card === card && roles.update(() => ({ history: { card, runs: [], error: String(e?.message || e) } })));
  }, [card, role, bio]);
  return (
    <section className="rl-history" data-testid="roles-live-history">
      <div className="rail-label mono">LAST RUNS UNDER THIS ROLE</div>
      {h.runs === null ? (
        <p className="muted">reading the history...</p>
      ) : h.runs.length ? (
        <ul>
          {h.runs.map((x, i) => (
            <li key={(x.session_id || "") + i}>
              <span className="mono muted">{ago(x.finished || x.started)} ago</span> <b>{x.bio || x.role}</b>{" "}
              <span className="og-chip mono" data-bad={x.is_error || undefined}>{x.is_error ? "failed" : x.status || ""}</span> <span className="mono">{cost(x.cost_usd)}</span>
              {x.session_id && (
                <button className="og-link mono" onClick={() => void openReplay(x.session_id!, "local")} data-testid="roles-history-replay"
                        title="Play this session back on the canvas: the cards light up in the order they worked">replay</button>
              )}
              {x.task && <div className="muted rl-task">{short(x.task, 140)}</div>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">{h.error || "No run under this role on this harness yet."}</p>
      )}
    </section>
  );
}

function Watched({ a }: { a: LiveAgent }) {
  const st = useFleet((s) => s.streams[a.key]) || EMPTY;
  const follow = useFleet((s) => s.follow);
  const pinned = useFleet((s) => s.pinned);
  const sub = useRoles((s) => s.liveSub);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (box.current && follow) box.current.scrollTop = box.current.scrollHeight;
  }, [st.tick, follow, sub, a.key]);
  const replay = a.key.startsWith("replay|");
  const off = replay || a.control === "none" || !isLiveAgent(a);
  const live = isLiveAgent(a);
  const here = useLocalAgent(replay ? "" : a.key);
  const subs: [LiveSub, string][] = [["thinking", "Thinking"], ["working", "Working"], ["output", "Output"]];
  return (
    <div className="rl-agent" data-key={a.key} data-testid="roles-live-agent">
      <header className="rl-head">
        <b>{a.name}</b>
        {a.role && a.role !== a.name && <span className="og-chip mono">{a.role}</span>}
        <span className="spacer" />
        {live && here && <WatchInSession agent={a.key} testid="roles-watch-session" />}
        <span className="og-badge mono" data-live={a.activity}>{a.state.toUpperCase()}</span>
      </header>
      <div className="mono muted rl-meta">
        {a.harness} · {short(a.session, 28)} · {a.model || "model ?"} · {cost(a.cost_usd)}
        {a.since && live ? ` · ${ago(a.since)}` : ""}
        {a.current ? ` · ${a.current}` : ""}
      </div>
      {a.task && (
        <details className="fa-task">
          <summary>What it was asked</summary>
          <p>{a.task}</p>
        </details>
      )}
      {replay ? (
        <p className="muted">A replay: the cards show the session as it ran. Close the bar under the canvas to come back to what runs now.</p>
      ) : (
        <>
          <div className="segmented" role="tablist" aria-label="Streams">
            {subs.map(([k, label]) => (
              <button key={k} role="tab" aria-selected={sub === k} className={sub === k ? "on" : ""} onClick={() => roles.update(() => ({ liveSub: k }))} data-testid={`roles-live-${k}`}>{label}</button>
            ))}
          </div>
          <div className="fa-stream rl-stream" ref={box} data-testid="roles-live-stream">
            {st.loading && !st.entries.length && <div className="og-wait mono muted">reading its stream...</div>}
            {st.error && <p className="og-problems">{st.error}</p>}
            {sub === "thinking" ? <ThinkingView entries={st.entries} live={live} /> : sub === "working" ? <WorkingView entries={st.entries} /> : <OutputView entries={st.entries} fallback="" live={live} />}
          </div>
          <div className="fa-controls">
            <Button size="sm" icon={<Icon name={a.state === "paused" ? "play" : "pause"} />} disabled={off} onClick={() => void togglePause(a.key)} title="P">{a.state === "paused" ? "Resume" : "Pause"}</Button>
            <Button size="sm" variant="danger" icon={<Icon name="stop" />} disabled={off} onClick={() => askStop(a.key)} title="It stops at its next step (asks first)" data-testid="roles-live-stop">Stop</Button>
            <Button size="sm" variant={follow ? "primary" : "ghost"} icon={<Icon name="follow" />} aria-pressed={follow} onClick={toggleFollow} title="F: the stream scrolls with it">Follow</Button>
            <Button size="sm" variant={pinned === a.key ? "primary" : "ghost"} icon={<Icon name="pin" />} aria-pressed={pinned === a.key} onClick={() => pin(pinned === a.key ? "" : a.key)} title="Space: keep its mini stream on screen">
              {pinned === a.key ? "Pinned" : "Pin"}
            </Button>
          </div>
          <Steer key={a.key} k={a.key} disabled={off} why={off ? "it takes no steer now" : undefined} />
        </>
      )}
    </div>
  );
}

export function LiveTab() {
  const sel = useRoles((s) => s.sel);
  const n = useRoles((s) => nodeById(s, s.sel));
  const watched = useRoles((s) => s.watched);
  const byNode = useByNode();
  const list = (sel && byNode[sel]) || [];
  const a = list.find((x) => x.key === watched) || list[0];
  useEffect(() => {
    if (a && a.key !== roles.get().watched) watchAgent(a.key);
  }, [a?.key]);
  if (!sel || !n) return <p className="muted" data-testid="roles-live">Select a card: the agents that run under it right now, or its last runs, show here. J / K hop between the working cards.</p>;
  if (!list.length || !a)
    return (
      <div className="rl" data-testid="roles-live">
        <header className="rl-head"><b>{n.alias && n.alias !== n.role ? `${n.agent} (${n.alias})` : n.agent}</b><span className="og-chip mono">nobody runs it now</span></header>
        <History card={sel} role={n.role} bio={n.agent} />
      </div>
    );
  return (
    <div className="rl" data-testid="roles-live">
      {list.length > 1 && (
        <div className="rl-chips">
          {list.map((x) => (
            <button key={x.key} className="og-chip rl-chip" aria-pressed={x.key === a.key} data-live={x.activity} onClick={() => watchAgent(x.key)} data-testid="roles-live-chip">
              {x.name} <small className="mono">{x.harness} · {x.state}</small>
            </button>
          ))}
        </div>
      )}
      <Watched a={a} />
    </div>
  );
}
