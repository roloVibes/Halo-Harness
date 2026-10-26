// session-live (3.1.5.0 R3, the owner: "the entire right side on the
// dashboard landing page is like scrolling visually seeing everything
// working in real time"): one auto-scrolling column of every agent of this
// harness at once -- what it types, each tool call and its result, what it
// hands back, what it asks you -- in the order it arrives (shared/liveFeed.ts
// and liveTree.ts; LiveRows.tsx draws the lines). Follow is on: scrolling up
// pauses it and "↓ N new" resumes. A tag pins its agent (the column shows only
// it; the tag again, or Esc, shows everyone). Hovering a line lights that
// agent's node on the map. The DOM holds the newest VIEW lines; older ones are
// in Activity. 3.1.7.0 R1 (the owner, from the Fleet view: "I want what fleet
// has with tool running too within the session tab. More of insight and
// ability to jump in and steer"), top to bottom: the header with the agent
// and kind picks beside Follow (LiveHead.tsx), Fleet's timeline strip for
// this session (a lane click pins its agent), the lines with Fleet's time and
// KIND columns, and the Steer box at the foot at all times (LiveSteer.tsx:
// the pinned agent, else the session's main agent, with Pause and Stop).
// 3.3.0.0 R6: the steer's target row is outlined (a click on a row, or `s` on
// a focused row, chooses it); the column stops following while you compose
// or have scrolled up (follow.ts: the "N new rows · follow" pill); Export
// downloads the session's trace (TraceExport.tsx).
import { useCallback, useEffect, useMemo, useRef, type KeyboardEvent } from "react";
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { patchPanel } from "../../lib/workspace/persist";
import { Metric } from "../orchestra/bits";
import { short } from "../orchestra/format";
import { Timeline } from "../fleet/Timeline";
import { allAgents, fleet, isLive, localId, useFleet } from "../fleet/store";
import { focusSteer } from "../fleet/Steer";
import { useLive, type LiveLine } from "../shared/liveFeed";
import { hueOf } from "../shared/hues";
import { startLiveTree } from "../shared/liveTree";
import { kindIn, LiveHead } from "./LiveHead";
import { answerAsk, LiveRow, type Who } from "./LiveRows";
import { LiveSteer } from "./LiveSteer";
import { useFollow } from "./follow";
import { chooseTarget, followAgain, pauseFollow, setPin, targetRow, useStripScope, useSteerTarget } from "./steer";
import { sess, useSession } from "./store";
import { TraceExport } from "./TraceExport";

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
const setHover = (key: string) => fleet.get().hover !== key && fleet.update(() => ({ hover: key }));

export function LiveDetail() {
  useEffect(() => startLiveTree(true), []);
  const here = useFleet((s) => localId(s));
  const all = useLive((s) => s.lines);
  const pin = useSession((s) => s.pin);
  const kind = useSession((s) => s.kind);
  const held = useSession((s) => s.held);
  const who = useWho();
  const strip = useStripScope();
  const target = useSteerTarget().key;
  const scroller = useRef<HTMLDivElement>(null);
  const lines = useMemo(() => all.filter(pin ? (l) => l.key === pin : mine(here)).filter(kindIn(kind)), [all, pin, here, kind]);
  const shown = useMemo(() => (lines.length > VIEW ? lines.slice(-VIEW) : lines), [lines]);
  const targetN = useMemo(() => targetRow(shown, target, held), [shown, target, held]);
  const { following, fresh, onScroll } = useFollow(scroller, shown);
  const onPin = useCallback((k: string) => setPin(k), []);
  const onTarget = useCallback((l: LiveLine) => chooseTarget(l.key, l.n), []);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("textarea, input, select") || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const row = (e.target as HTMLElement).closest<HTMLElement>(".slv-line");
    const ask = ["a", "r", "s", "o"].includes(k) ? [...shown].reverse().find((l) => l.kind === "ask") : undefined;
    if (k === "s" && row?.dataset.key) {
      chooseTarget(row.dataset.key, Number(row.dataset.n) || 0); // `s` on a focused row: steer it
      focusSteer("live");
    } else if (k === "Escape" && sess.get().pin) setPin(sess.get().pin);
    else if (!(ask && answerAsk(ask.key, k, true))) return; // A / R / S / O: the newest ask card in the column
    e.preventDefault();
    e.stopPropagation();
  };
  const working = [...who.entries()].filter(([k, w]) => k.startsWith(here + "|") && w.state === "running").length;
  const lastN = shown[shown.length - 1]?.n;
  const onFollow = () => (sess.get().follow ? pauseFollow() : followAgain());
  return (
    <div className="slv" data-testid="session-live-detail" data-follow={following || undefined} data-pinned={pin || undefined} data-kind={kind || undefined} data-target={target || undefined} onKeyDown={onKey}>
      <LiveHead working={working} count={lines.length} onFollow={onFollow} following={following} />
      <div className="slv-strip">
        <Timeline scope={strip} onPick={onPin} marked={target} verb="show only it in Live (again: everyone)" testid="session-live-timeline" extra={<TraceExport where="timeline" />} />
      </div>
      <div className="slv-rows">
        <div className="slv-scroll" ref={scroller} onScroll={onScroll} onMouseLeave={() => setHover("")} data-testid="session-live-scroll" tabIndex={-1}>
          {lines.length > VIEW && (
            <button type="button" className="og-link mono slv-older" data-testid="session-live-older" onClick={() => patchPanel("session", "session-activity", { collapsed: false }, false)}>
              {lines.length - VIEW} older line{lines.length - VIEW === 1 ? "" : "s"}: the full log is in Activity
            </button>
          )}
          {!shown.length && (
            <Empty title={pin || kind ? "Nothing of that yet" : "Waiting for the agents"} testid="session-live-empty"
                   body={kind ? "No line of that kind yet: every kind shows them all." : "Every agent's text, tool calls and output land here the moment they happen: start or steer a session in a terminal (halo)."} />
          )}
          {shown.map((l) => (
            <LiveRow key={l.n} l={l} who={who.get(l.key) || { name: l.key.split("|")[2] || "?", hc: hueOf(l.key), state: "" }} last={l.n === lastN} target={l.n === targetN}
                     onPin={onPin} onHover={setHover} onTarget={onTarget} />
          ))}
        </div>
        {fresh > 0 && (
          <button type="button" className="slv-new mono" data-testid="live-follow" onClick={followAgain} title="Follow the newest row again">
            {fresh} new row{fresh === 1 ? "" : "s"} · follow
          </button>
        )}
      </div>
      <footer className="slv-foot">
        <LiveSteer />
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
