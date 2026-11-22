// The wait of a run, on BOTH run drawings (P4 batch 13's repair; the coordinator's ruling: nothing a person could see of a
// run in 3.6.0.1 is lost). As 3.6.0.0's lit Map computed them (crew/live/waits.ts, useWaits.ts, narrate.ts): each agent's
// wait and the waiting path, from the session's record and the feed, while the drawing is shown (a hidden drawing leaves
// the waits' store alone), for
// - the outline: the box the whole session waits on -- the end of the waiting path, so also a box whose agent or row
//   waits on a tool, a model reply or a helper, not only one waiting on you -- carries `data-waited` (DownBox.tsx);
// - the wait link: 3.6.0.0's words for it ("waiting on: tester -> Bash pytest -q", "waiting on you: ...") on its own row
//   (WaitRow; Session: beside "more below" in the bottom slot; Live: the tools row, left of the zoom), its words whole and
//   wrapped (P8, the owner's rule: a text is never cut; P8 batch 3: narrate.ts waitWords whole, the one-line sentence
//   keeps its bound), in room reserved from the first draw by hidden twins of a usual link of this run (an agent's name,
//   a tool's words of 36 characters, a question of 48 and "(and n more)"), so a usual wait coming or going moves
//   nothing; a longer link takes its room when the wait appears, as a hidden twin of its REAL words that stays until the
//   wait's words really change (a wait going moves nothing); a press brings that box into view and picks it as a click
//   does (its card opens);
// - the clock of a waiting box or row (runParts.tsx ToolClock): what it waits for and for how long.
import { useContext, useMemo, useRef, type RefObject } from "react";
import { useSessionRecord } from "../../../lib/work/record";
import { fleet } from "../../fleet/store";
import { liveNodes, type LiveNode } from "../live/liveModel";
import { waitWords } from "../live/narrate";
import { useWaits } from "../live/useWaits";
import type { Overlay } from "./overlay";
import { NO_WAIT, RunCtx, type RunWait } from "./runParts";
import { boxOfAgent } from "./talkPulse";
import { waitRoom } from "./truth";

const NO_NODES: LiveNode[] = [];

/** The run's wait for session `sid` drawn as `ov`, at `now` (seconds), computed only while `on` (the drawing is shown). */
export function useRunWait(sid: string, ov: Overlay | null, now: number, on: boolean): RunWait {
  const rec = useSessionRecord(on ? sid : "");
  const nodes = useMemo(() => (rec && on ? liveNodes(rec, fleet.get(), now * 1000) : NO_NODES), [rec, now, on]);
  const { waits, path, recent } = useWaits(nodes, now * 1000, on);
  return useMemo(() => {
    const leaf = path.leaf?.id || "";
    const room = waitRoom(nodes.map((n) => (n.role && n.role !== n.name ? n.role : n.name)));
    if (!on || !leaf || !ov) return on ? { ...NO_WAIT, waits, room, recent } : NO_WAIT;
    const box = boxOfAgent(ov, true).get(leaf) || "";
    return { waits, leaf, box, link: waitWords(nodes, waits, path, true), room, recent };
  }, [waits, path, nodes, ov, on, recent]);
}

/** The wait link's own row: its room is the tallest of the twins -- a usual link's, from the first draw, and the last
 *  wait's REAL words, from the draw its link first shows in (P8 batch 3) -- so the link wraps whole inside it, never cut. */
export function WaitRow({ world }: { world: RefObject<HTMLElement | null> }) {
  const w = useContext(RunCtx)?.wait;
  const last = useRef("");
  if (w?.link) last.current = w.link; // kept when the wait goes: only new words change the room
  const twins = [...(w?.room?.length ? w.room : waitRoom([])), ...(last.current ? [last.current] : [])];
  return (
    <div className="mp-wait-row" data-testid="run-wait-row">
      {twins.map((t, i) => <span key={i} className="mp-wait-twin" aria-hidden="true">{t}</span>)}
      <WaitLink world={world} />
    </div>
  );
}

/** The drawn box (or made-up helper's box) the session waits on, in `world`. */
export function waitedBox(world: HTMLElement | null, w: RunWait): HTMLElement | null {
  if (!world || !w.leaf) return null;
  return world.querySelector<HTMLElement>(w.box ? `:scope > [data-box="${CSS.escape(w.box)}"]` : `:scope > [data-helper="${CSS.escape(w.leaf)}"]`);
}

/** The wait link: the box the session waits on, into view and picked as a click picks it. Nothing when nothing waits. */
export function WaitLink({ world }: { world: RefObject<HTMLElement | null> }) {
  const w = useContext(RunCtx)?.wait;
  if (!w?.link) return null;
  const show = () => {
    const el = waitedBox(world.current, w);
    if (!el) return;
    if (!el.hasAttribute("data-selected")) el.click();
    el.scrollIntoView({ block: "nearest", inline: "nearest" });
    el.focus({ preventScroll: true });
  };
  return (
    <button type="button" className="mp-link mp-wait-link" onClick={show} data-testid="run-wait" data-leaf={w.leaf}
            title={`${w.link}\nBring the box it waits on into view, and open it`}><span className="mp-wait-words">{w.link}</span></button>
  );
}
