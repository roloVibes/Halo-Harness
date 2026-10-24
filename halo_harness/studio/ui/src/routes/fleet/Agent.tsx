// fleet-agent: the inspector for the selected agent. The header (harness,
// session, role, model, cost, elapsed, state), what it was asked, its three
// streams (Thinking / Working / Output, tabbed or side by side), Pause /
// Resume, Stop (asks first), Follow (the stream scrolls with it), Pin (the
// mini stream) and the Steer box. Opening an agent loads its backlog
// (`agent_tail`) and follows it (`agent_follow`), so the rest is pushed.
// R4: Take over, Hand to..., Record and Replay under the controls; with no
// agent picked, this harness's last sessions to replay (AgentHistory.tsx).
// 3.2.0.0 R4: a mission part's agent shows its packs' inspector lines (PackCaps.tsx).
import { useEffect, useRef, type ReactNode } from "react";
import { Button, Empty, Icon, Kbd } from "../../lib/ui";
import type { MotionState } from "../../lib/motion";
import { cost, elapsed, short } from "../orchestra/format";
import { askStop, pin, toggleFollow, togglePause } from "./actions";
import { AgentExtras, RecentSessions } from "./AgentHistory";
import { nowText } from "./MapNode";
import { AgentPackInspector } from "./PackCaps";
import { Steer } from "./Steer";
import { EMPTY, outputOf, thinkingOf, workingOf } from "./streams";
import { OutputView, ThinkingView, Typed, WorkingView } from "./StreamViews";
import { agentMotion, fleet, isLive, saveOpts, sessionTitle, useFleet, useNow, useSelected, type StreamTab } from "./store";

const FINISHED = ["done", "failed", "stopped"];

function Head() {
  const ref = useSelected();
  const now = useNow(!!ref && isLive(ref.a));
  if (!ref) return null;
  const { a, s, h } = ref;
  const since = Number(a.since) || 0;
  return (
    <header className="fa-head">
      <div className="fa-head-row">
        <span className="og-badge mono" data-state={a.state === "running" ? "running" : a.state === "done" ? "finished" : a.state === "failed" || a.state === "stopped" ? "stopped" : a.state === "waiting" || a.state === "paused" ? "interrupted" : "none"}>
          {String(a.state || "?").toUpperCase()}
        </span>
        <b className="fa-name">{a.name || a.agent_id}</b>
        {a.role && a.role !== a.name && <span className="og-chip mono">{a.role}</span>}
        <span className="spacer" />
        <span className="mono fa-cost" title="what it has cost so far">{cost(a.cost_usd)}</span>
      </div>
      <div className="fa-meta mono muted">
        {h.name || h.id.slice(0, 8)} · {short(sessionTitle(s), 28)} · {a.model || "model ?"}
        {since > 0 && isLive(a) && ` · ${elapsed(now / 1000 - since)}`}
        {a.turns ? ` · ${a.turns} turn${a.turns === 1 ? "" : "s"}` : ""}
      </div>
    </header>
  );
}

function Tabs({ counts }: { counts: Record<StreamTab, number> }) {
  const tab = useFleet((s) => s.tab);
  const labels: Record<StreamTab, string> = { thinking: "Thinking", working: "Working", output: "Output" };
  return (
    <div className="segmented fa-tabs" role="tablist" aria-label="Streams">
      {(Object.keys(labels) as StreamTab[]).map((t) => (
        <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => fleet.update(() => ({ tab: t }))} data-testid={`fleet-tab-${t}`}>
          {labels[t]} {t !== "output" && <span className="fa-count mono">{counts[t]}</span>}
        </button>
      ))}
    </div>
  );
}

function Col({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="fa-col">
      <div className="rail-label mono">{title}</div>
      {children}
    </section>
  );
}

export function AgentDetail() {
  const ref = useSelected();
  const st = useFleet((s) => (ref ? s.streams[ref.key] : undefined)) || EMPTY;
  const tab = useFleet((s) => s.tab);
  const columns = useFleet((s) => s.columns);
  const follow = useFleet((s) => s.follow);
  const pinned = useFleet((s) => s.pinned);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scroller.current;
    if (el && follow) el.scrollTop = el.scrollHeight;
  }, [st.tick, follow, tab, ref?.key]);
  if (!ref)
    return (
      <div className="fa-none">
        <Empty title="Pick an agent" body="Click an agent on the map (or press J / K to hop between the live ones): what it thinks, does and writes shows here, and you can steer it." testid="fleet-agent-empty" />
        <RecentSessions />
      </div>
    );
  const { a, key, h } = ref;
  const live = isLive(a);
  const done = FINISHED.includes(String(a.state));
  const noControl = h.allow_control === "none";
  const why = noControl ? `${h.name || "that harness"} takes no commands from here (allow_control none)` : undefined;
  const task = st.entries.find((e) => e.kind === "user" && !e.you)?.text || a.task || "";
  const views: Record<StreamTab, ReactNode> = {
    thinking: <ThinkingView entries={st.entries} live={live} />,
    working: <WorkingView entries={st.entries} />,
    output: <OutputView entries={st.entries} fallback={done ? a.last_text || "" : ""} live={live} />,
  };
  return (
    <div className="fa" data-state={a.state} data-key={key} data-testid="fleet-agent-detail">
      <Head />
      {task && (
        <details className="fa-task">
          <summary>What it was asked</summary>
          <p>{task}</p>
        </details>
      )}
      {columns === "columns" ? null : <Tabs counts={{ thinking: thinkingOf(st.entries).length, working: workingOf(st.entries).length, output: 0 }} />}
      <div className="fa-stream" ref={scroller} data-testid="fleet-stream" data-columns={columns === "columns" || undefined}>
        {st.loading && !st.entries.length && <div className="og-wait mono muted">reading its backlog...</div>}
        {st.error && <p className="og-problems">{st.error}</p>}
        {columns === "columns" ? (
          <>
            <Col title="THINKING">{views.thinking}</Col>
            <Col title="WORKING">{views.working}</Col>
            <Col title="OUTPUT">{views.output}</Col>
          </>
        ) : (
          views[tab]
        )}
      </div>
      <div className="fa-controls">
        <Button size="sm" icon={<Icon name={a.state === "paused" ? "play" : "pause"} />} disabled={done || noControl} onClick={() => void togglePause(key)} title={why || "P"} data-testid="fleet-pause">
          {a.state === "paused" ? "Resume" : "Pause"}
        </Button>
        <Button size="sm" variant="danger" icon={<Icon name="stop" />} disabled={done || noControl} onClick={() => askStop(key)} title={why || "Stops at its next step (asks first)"} data-testid="fleet-stop">
          Stop
        </Button>
        <Button size="sm" variant={follow ? "primary" : "ghost"} icon={<Icon name="follow" />} aria-pressed={follow} onClick={toggleFollow} title="F: the stream scrolls with it">
          Follow
        </Button>
        <Button size="sm" variant={pinned === key ? "primary" : "ghost"} icon={<Icon name="pin" />} aria-pressed={pinned === key} onClick={() => pin(pinned === key ? "" : key)} title="Space: keep its mini stream on screen">
          {pinned === key ? "Pinned" : "Pin"}
        </Button>
        <span className="spacer" />
        <span className="fa-keys muted"><Kbd keys="J" /> <Kbd keys="K" /> hop</span>
      </div>
      <AgentExtras r={ref} done={done} noControl={noControl} />
      <AgentPackInspector mission={ref.s.mission} part={ref.s.part} />
      <Steer key={key} k={key} disabled={done || noControl} why={why} />
    </div>
  );
}

export function AgentGlance() {
  const ref = useSelected();
  const st = useFleet((s) => (ref ? s.streams[ref.key] : undefined)) || EMPTY;
  if (!ref) return <div className="glance"><div className="glance-text">No agent picked</div><div className="glance-hint">Click one on the map, or J / K.</div></div>;
  const text = outputOf(st.entries) || ref.a.last_text || "";
  return (
    <div className="glance fa-glance">
      <div className="glance-kicker mono">{String(ref.a.state || "").toUpperCase()} · {cost(ref.a.cost_usd)}</div>
      <div className="glance-text">{ref.a.name || ref.a.agent_id}</div>
      <div className="glance-hint mono">{nowText(ref.a)}</div>
      {text && <div className="fa-glance-text"><Typed text={short(text, 240)} live={isLive(ref.a)} /></div>}
    </div>
  );
}

export function AgentSettings() {
  const columns = useFleet((s) => s.columns);
  return (
    <div className="segmented" role="group" aria-label="Streams">
      {(["tabs", "columns"] as const).map((c) => (
        <button key={c} className={columns === c ? "on" : ""} aria-pressed={columns === c} onClick={() => (fleet.update(() => ({ columns: c })), saveOpts())}>
          {c === "tabs" ? "One stream at a time" : "Three side by side"}
        </button>
      ))}
    </div>
  );
}

export function useAgentMotion(): MotionState {
  const ref = useSelected();
  const doneAt = useFleet((s) => (ref ? s.doneAt[ref.key] || 0 : 0));
  return ref ? agentMotion(ref.a, doneAt) : "none";
}
