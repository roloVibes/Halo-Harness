// What the 3.6.0.0 lit Map showed of a run, on BOTH run drawings (P4 batch 13, the coordinator's ruling: nothing a person
// could see of a run in 3.6.0.1 is lost): Session's Live drawer (routes/session/MapDown.tsx) and Agents -> 4 · Live
// (routes/agents/LiveDraw.tsx) import these parts, never a copy.
// - the tool clock: a working box or row shows the tool it is in and for how long ("Bash · 12 s", truth.ts toolClock),
//   from the feed's open tool rows (shared/liveFeed.ts `open`), ticking with the drawing's one-second clock (LitMini
//   useLit `now`); the row is there while the box works and the seconds sit in a slot of fixed width, so a tick never
//   moves anything; the clock runs only while the drawing is shown (useShown: no timer of a hidden drawing);
// - the talk pulse: an `agent_talk` frame between agents of two boxes lights the line between them for TALK_S seconds
//   (talkPulse.ts; RunLine `data-talk`), never a line the words did not travel;
// - '+{n} under it': a box whose rows are not all drawn says how many more, and a press opens the Feed on that agent's
//   `under:` page (RunRows.tsx KidRows; the drawing says where the Feed is: `RunCtx.under`);
// - J / K: step the selection (the step-in card, `data-selected`) from box to box in drawing order, as a click does;
//   never while a text box (the card's Steer field) has the focus.
// - the wait (batch 13's repair, runWait.tsx): the clock also runs while a box or row waits ("waiting for you · 12 s").
import { createContext, useContext, useEffect, useMemo, type KeyboardEvent, type RefObject } from "react";
import { studio, useStore } from "../../../lib/store";
import { live, useLive } from "../../shared/liveFeed";
import { useTalks } from "../../shared/liveTalk";
import { startLiveTree } from "../../shared/liveTree";
import { useAgentsView } from "../../agents/store";
import { secsWords, type Recent, type Wait } from "../live/waits";
import { NO_NOW, nowOf, type Now } from "./nowLine";
import { lineKey, type Overlay } from "./overlay";
import { talkPulses, type TalkPulse } from "./talkPulse";
import { toolClock, waitClock } from "./truthBits";
import { waitWhat } from "./truth";

/** The run's wait (runWait.tsx): `waits` by agent id; `leaf`: the agent the session waits on; `box`: the drawn box
 *  holding it; `link`: 3.6.0.0's words for it; `room`: the longest links this run can show (P8: the link's reserved room). */
export type RunWait = { waits: Map<string, Wait>; leaf: string; box: string; link: string; room: string[];
  /** 3.6.0.13 L2a: each agent's newest lines by its feed key (useWaits.ts) */ recent: Map<string, Recent> };
export const NO_WAIT: RunWait = { waits: new Map(), leaf: "", box: "", link: "", room: [], recent: new Map() };

/** What the parts of one drawing read: its agents' keys by id, its clock (`now`, seconds), its Feed door, its wait, and
 *  `held`: the drawing is held (hold.ts: the pointer on it or a card open; 3.6.0.13 L2b, NOW's one growth waits). */
export type RunParts = { keys: Map<string, string>; now: number; under: (aid: string) => void; wait: RunWait; held: boolean };
export const RunCtx = createContext<RunParts | null>(null);

/** The drawing is on screen: Session's drawer while Session is the section; 4 · Live while Agents shows Live. */
export function useShown(where: "session" | "live"): boolean {
  const section = useStore(studio, (s) => s.section);
  const view = useAgentsView();
  return where === "session" ? section === "session" : section === "agents" && view === "live";
}

/** The parts' context for one drawing (`agents`: the session's agents, id -> feed key). */
export function useRunParts(agents: { id: string; key: string }[], now: number, under: (aid: string) => void, wait: RunWait = NO_WAIT,
  held = false): RunParts {
  useEffect(() => startLiveTree(), []); // the feed's open tools and its TALK frames
  const keys = useMemo(() => new Map(agents.map((a) => [a.id, a.key])), [agents]);
  return useMemo(() => ({ keys, now, under, wait, held }), [keys, now, wait, held]); // eslint-disable-line react-hooks/exhaustive-deps
}

/** 3.6.0.13 L1 L2a: NOW of agent `aid` (its raw state, since and end in seconds; 0 unknown) at the drawing's one clock,
 *  from the feed's open tool for its key, its newest line and its wait (nowLine.ts). No timer, no fetch. */
export function useNowOf(aid: string, raw: string, started: number, ended: number): Now {
  const P = useContext(RunCtx);
  const open = useLive((s) => s.open);
  if (!P) return NO_NOW;
  const key = P.keys.get(aid) || "";
  const t = key ? open[key] : undefined;
  return nowOf({ raw, started, ended, tool: t ? { tool: t.tool, t0: t.t0 } : null, last: key ? P.wait.recent.get(key)?.last || null : null,
    wait: P.wait.waits.get(aid) || null }, P.now * 1000);
}


/** The tool clock of the agents `aids` while `on` (the box or row works or waits): its row is kept while it does, the
 *  tool and its seconds when one is open, else what it waits for and since when (runWait.tsx; 3.6.0.0's clock ran for a
 *  working or a waiting box). */
export function ToolClock({ aids, on }: { aids: string[]; on: boolean }) {
  const P = useContext(RunCtx);
  const open = useLive((s) => s.open);
  if (!P || !on) return null;
  const t = aids.map((id) => open[P.keys.get(id) || ""]).find(Boolean);
  const w = t ? undefined : aids.map((id) => P.wait.waits.get(id)).find((x) => !!x?.since && x.kind !== "nothing");
  const secs = t ? secsWords(t.t0, P.now * 1000) : w ? secsWords(w.since, P.now * 1000) : "";
  const say = (s: string) => (t ? toolClock(t.tool, s) : w ? waitClock(waitWhat(w.kind === "you" || w.kind === "model" ? w.kind : w.what), s) : "");
  return (
    <span className="mp-lit-row mono mp-clock" data-testid="run-clock" data-tool={t?.tool || undefined} data-wait={w?.kind}
          title={t || w ? say(secs) : undefined}>
      {t || w ? <>{say("")}<span className="mp-clock-secs" data-testid="run-clock-secs">{secs}</span></> : " "}
    </span>
  );
}

/** The talk pulses of session `sid` now, by the drawn line they travel (`from>to` either way round); none on a line
 *  the words did not travel. */
export function useTalkLines(ov: Overlay | null, sid: string, now: number, drawn: { from: string; to: string }[]): Map<string, TalkPulse> {
  const msgs = useTalks((t) => t.msgs);
  return useMemo(() => {
    const out = new Map<string, TalkPulse>();
    if (!ov) return out;
    const has = new Set(drawn.map((l) => lineKey(l.from, l.to)));
    for (const p of talkPulses(msgs, live.get().lines, ov, sid, now, true)) {
      const k = has.has(lineKey(p.from, p.to)) ? lineKey(p.from, p.to) : has.has(lineKey(p.to, p.from)) ? lineKey(p.to, p.from) : "";
      if (k) out.set(k, p);
    }
    return out;
  }, [msgs, ov, sid, now, drawn]);
}

const TYPING = "input, textarea, select, [contenteditable]";

/** J / K inside the drawing: the next (previous) box in drawing order is picked as a click picks it, then focused and
 *  brought into view. `across`: the drawing runs left to right (columns first), else top to bottom (rows first). */
export function useStepKeys(world: RefObject<HTMLElement | null>, across: boolean): (e: KeyboardEvent<HTMLElement>) => void {
  return (e) => {
    const k = e.key.toLowerCase();
    if (e.ctrlKey || e.metaKey || e.altKey || (k !== "j" && k !== "k") || (e.target as Element | null)?.closest?.(TYPING)) return;
    const pos = (b: HTMLElement): [number, number] => [parseFloat(b.style.left) || 0, parseFloat(b.style.top) || 0];
    const all = [...(world.current?.querySelectorAll<HTMLElement>(":scope > [data-box]") || [])].sort((a, b) => {
      const [ax, ay] = pos(a), [bx, by] = pos(b);
      return across ? ax - bx || ay - by : ay - by || ax - bx;
    });
    if (!all.length) return;
    e.preventDefault(); // Session's own J / K (fleet/hop.ts) leave it alone
    const at = all.findIndex((b) => b.hasAttribute("data-selected"));
    const from = at >= 0 ? at : all.findIndex((b) => b === document.activeElement);
    const next = all[from < 0 ? (k === "j" ? 0 : all.length - 1) : (from + (k === "j" ? 1 : -1) + all.length) % all.length];
    next.click();
    next.focus({ preventScroll: true });
    next.scrollIntoView({ block: "nearest", inline: "nearest" });
  };
}
