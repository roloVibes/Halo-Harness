// session-live (3.1.5.0 R3, the owner: "the entire right side on the
// dashboard landing page is like scrolling visually seeing everything
// working in real time"): one auto-scrolling column of every agent of this
// harness at once -- what it types, each tool call and its result, what it
// hands back, what it asks you -- in the order it arrives (shared/liveFeed.ts
// and liveTree.ts; LiveRows.tsx draws the lines). Follow is on: scrolling up
// pauses it and "↓ N new" resumes. A tag pins its agent (the column shows only
// it; the tag again, or Esc, shows everyone), and the Steer box at the bottom
// talks to the pinned agent. Hovering a line lights that agent's node on the
// map. The DOM holds the newest VIEW lines; older ones are in Activity.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Empty, Icon } from "../../lib/ui";
import { patchPanel } from "../../lib/workspace/persist";
import { Metric } from "../orchestra/bits";
import { short } from "../orchestra/format";
import { select } from "../fleet/actions";
import { Steer } from "../fleet/Steer";
import { allAgents, fleet, findAgent, isLive, localId, useFleet } from "../fleet/store";
import { useLive, type LiveLine } from "../shared/liveFeed";
import { hueOf } from "../shared/hues";
import { startLiveTree } from "../shared/liveTree";
import { answerAsk, LiveRow, type Who } from "./LiveRows";
import { sess, useSession } from "./store";

export const VIEW = 500;
const whoCache = new Map<string, Who>();

/** Every agent this harness has, by key: its name, colour and state (the same object while they hold, so a line redraws only when its agent changed). */
function useWho(): Map<string, Who> {
  const harnesses = useFleet((s) => s.harnesses);
  return useMemo(() => {
    const out = new Map<string, Who>();
    for (const r of allAgents({ ...fleet.get(), harnesses })) {
      const w = { name: r.a.name || r.a.role || r.a.agent_id, hc: hueOf(r.key), state: String(r.a.state || "") };
      const was = whoCache.get(r.key);
      const keep = was && was.name === w.name && was.hc === w.hc && was.state === w.state ? was : w;
      whoCache.set(r.key, keep);
      out.set(r.key, keep);
    }
    return out;
  }, [harnesses]);
}

const mine = (here: string) => (l: LiveLine) => l.key.startsWith(here + "|");

export function setPin(key: string): void {
  const next = sess.get().pin === key ? "" : key;
  sess.update(() => ({ pin: next, follow: true }));
  if (next && findAgent(fleet.get(), next)) select(next);
}

const setHover = (key: string) => fleet.get().hover !== key && fleet.update(() => ({ hover: key }));

export function LiveDetail() {
  useEffect(() => startLiveTree(true), []);
  const here = useFleet((s) => localId(s));
  const all = useLive((s) => s.lines);
  const pin = useSession((s) => s.pin);
  const follow = useSession((s) => s.follow);
  const who = useWho();
  const scroller = useRef<HTMLDivElement>(null);
  const [pausedAt, setPausedAt] = useState(0);
  const lines = useMemo(() => all.filter(pin ? (l) => l.key === pin : mine(here)), [all, pin, here]);
  const shown = lines.length > VIEW ? lines.slice(-VIEW) : lines;
  const fresh = follow ? 0 : shown.filter((l) => l.n > pausedAt).length;
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && follow) el.scrollTop = el.scrollHeight;
  }, [shown, follow]);
  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (!bottom && follow) {
      setPausedAt(shown[shown.length - 1]?.n || 0);
      sess.update(() => ({ follow: false }));
    } else if (bottom && !follow) sess.update(() => ({ follow: true }));
  };
  const onPin = useCallback((k: string) => setPin(k), []);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("textarea, input") || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const ask = ["a", "r", "s", "o"].includes(k) ? [...shown].reverse().find((l) => l.kind === "ask") : undefined;
    if (k === "Escape" && sess.get().pin) setPin(sess.get().pin);
    else if (!(ask && answerAsk(ask.key, k, true))) return; // A / R / S / O: the newest ask card in the column
    e.preventDefault();
    e.stopPropagation();
  };
  const pinned = pin ? findAgent(fleet.get(), pin) : null;
  const working = [...who.entries()].filter(([k, w]) => k.startsWith(here + "|") && w.state === "running").length;
  const lastN = shown[shown.length - 1]?.n;
  const done = !pinned || ["done", "failed", "stopped"].includes(String(pinned.a.state));
  return (
    <div className="slv" data-testid="session-live-detail" data-follow={follow || undefined} data-pinned={pin || undefined} onKeyDown={onKey}>
      <header className="slv-head">
        <span className="glance-kicker mono">LIVE</span>
        <span className="mono muted slv-counts" data-testid="session-live-counts">
          {working} working · {lines.length} line{lines.length === 1 ? "" : "s"}
        </span>
        {pinned && (
          <button type="button" className="slv-pinned mono" data-testid="session-live-pinned" onClick={() => setPin(pin)} title="Show every agent again (Esc)">
            only {short(pinned.a.name || pinned.a.agent_id, 20)} <Icon name="close" size={12} />
          </button>
        )}
        <span className="spacer" />
        <Button size="sm" variant={follow ? "primary" : "ghost"} icon={<Icon name="follow" />} aria-pressed={follow} data-testid="session-live-follow"
                onClick={() => (follow && setPausedAt(lastN || 0), sess.update((s) => ({ follow: !s.follow })))} title="Keep the newest line in view; scrolling up pauses it">
          Follow
        </Button>
      </header>
      <div className="slv-scroll" ref={scroller} onScroll={onScroll} onMouseLeave={() => setHover("")} data-testid="session-live-scroll" tabIndex={-1}>
        {lines.length > VIEW && (
          <button type="button" className="og-link mono slv-older" data-testid="session-live-older" onClick={() => patchPanel("session", "session-activity", { collapsed: false }, false)}>
            {lines.length - VIEW} older line{lines.length - VIEW === 1 ? "" : "s"}: the full log is in Activity
          </button>
        )}
        {!shown.length && (
          <Empty title={pin ? "Nothing from it yet" : "Waiting for the agents"} body="Every agent's text, tool calls and output land here the moment they happen: start or steer a session in a terminal (halo)." testid="session-live-empty" />
        )}
        {shown.map((l) => (
          <LiveRow key={l.n} l={l} who={who.get(l.key) || { name: l.key.split("|")[2] || "?", hc: hueOf(l.key), state: "" }} last={l.n === lastN} onPin={onPin} onHover={setHover} />
        ))}
      </div>
      {fresh > 0 && (
        <button type="button" className="slv-new mono" data-testid="session-live-new" onClick={() => sess.update(() => ({ follow: true }))}>
          ↓ {fresh} new
        </button>
      )}
      <footer className="slv-foot">
        {pinned ? (
          <Steer key={pin} k={pin} disabled={done} why={done ? "It has finished: nothing to steer" : undefined} />
        ) : (
          <div className="slv-hint mono muted" data-testid="session-live-hint">Click a tag to follow one agent and steer it here.</div>
        )}
      </footer>
    </div>
  );
}

export function LiveGlance() {
  const here = useFleet((s) => localId(s));
  const last = useLive((s) => {
    for (let i = s.lines.length - 1; i >= 0; i--) if (s.lines[i].key.startsWith(here + "|")) return s.lines[i];
    return undefined;
  });
  const harnesses = useFleet((s) => s.harnesses);
  const working = useMemo(() => allAgents({ ...fleet.get(), harnesses }).filter((r) => r.h.id === here && r.a.state === "running").length, [harnesses, here]);
  return (
    <div className="glance" data-testid="session-live-glance">
      <div className="glance-numbers">
        <Metric value={working} label="working now" tone={working ? "accent" : undefined} />
      </div>
      <div className="glance-hint">{last ? short(last.kind === "tool" ? `${last.tool} ${last.target || ""}` : last.text, 90) : "Every agent's lines land here as they happen."}</div>
    </div>
  );
}

export function useLiveMotion(): MotionState {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  return useMemo(() => {
    const rows = allAgents({ ...fleet.get(), harnesses }).filter((r) => r.h.id === here);
    if (rows.some((r) => r.a.state === "waiting")) return "waiting";
    return rows.some((r) => r.a.state === "running") ? "working" : rows.some((r) => isLive(r.a)) ? "idle" : "none";
  }, [harnesses, here]);
}
