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
// 3.1.9.0 R2: an `auto` member shows why it runs on its model ("auto: <model> -- <reason>").
// 3.3.11.0 R2: on Roles Live the tab follows the agent clicked on the tree (matched to a card or not, live or done).
// 3.3.16.0 R2 "the Fleet fold": the agent itself is the one agent inspector (routes/fleet/Agent.tsx AgentView: Fleet's
// Agent panel and this tab were two; the streams, controls, hand-offs, Record and Steer are drawn there once).
import { useEffect } from "react";
import { api } from "../../lib/api";
import { cost, short } from "../orchestra/format";
import { openReplay } from "../fleet/replay";
import { AgentView, useAgentRef } from "../fleet/Agent";
import { useByNode, watchAgent } from "./live";
import { nodeById, roles, useRoles } from "./store";
import type { HistoryRun } from "./types";

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

/** The agent watched: the one agent inspector (fleet/Agent.tsx AgentView, 3.3.16.0 R2), or a replay's line. */
export function Watched({ k }: { k: string }) {
  const r = useAgentRef(k.startsWith("replay|") ? "" : k);
  return (
    <div className="rl-agent" data-key={k} data-testid="roles-live-agent">
      {r ? <AgentView r={r} /> : k.startsWith("replay|") ? (
        <p className="muted">A replay: the cards show the session as it ran. Close the bar under the canvas to come back to what runs now.</p>
      ) : (
        <p className="muted">That agent is no longer in the frames.</p>
      )}
    </div>
  );
}

export function LiveTab() {
  const liveView = useRoles((s) => s.canvasView === "live");
  const viewed = useRoles((s) => s.watched);
  const sel = useRoles((s) => s.sel);
  const n = useRoles((s) => nodeById(s, s.sel));
  const watched = useRoles((s) => s.watched);
  const byNode = useByNode();
  const list = (sel && byNode[sel]) || [];
  const a = list.find((x) => x.key === watched) || list[0];
  useEffect(() => {
    if (!liveView && a && a.key !== roles.get().watched) watchAgent(a.key);
  }, [a?.key]);
  if (liveView && viewed)
    return (
      <div className="rl" data-testid="roles-live" data-view="live">
        <Watched k={viewed} />
      </div>
    );
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
      <Watched k={a.key} />
    </div>
  );
}
