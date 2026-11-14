// Agents -> Live (3.3.11.0 R2 as Roles Live; rolo 2026-11-02: "the roles tab kept up with what's happening during
// sessions for better map views"): the Canvas panel's Live face, the real agent tree on the whole canvas -- one node
// per agent the work record holds (lib/work/record.ts: live, or finished and still in the frames), parent -> child
// edges, nothing dropped (liveModel.ts), each lineup card the agents match as a faint group behind them, an `auto`
// pick's reason on its node, laid out in layers (liveLayout.ts) with zoom and Fit. 3.3.16.0 R1: a live Orchestra run
// joins the tree (routes/agents/live/runLanes.tsx). 3.3.16.0 R2 "the Fleet fold" (a machine's agents in Agents): the
// bar's scope switch -- **this halo** (one session of this harness, the picker) or **fleet** (every machine, its
// sessions, their agents, the open mission's parts under the machine each runs on; the Fleet Map drew this before and
// is gone) -- with the spawn / message edges lighting and the conflict edge; a click puts what it hit in the inspector
// (InspectorDetail: the fleet at a glance, a machine, an agent, a part), a click on the canvas itself clears it. The
// same component is Session's Map (`thumb`): this harness's sessions and their agents, fitted to the panel, a click
// picks the Steer box's target, "Open in Agents Live" opens the full tree. 3.3.16.1: each box of the full tree has its
// hover card (routes/agents/hover); the thumbnail keeps its plain tooltips.
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { Empty } from "../../lib/ui";
import { useFleet } from "../fleet/store";
import { startFleet } from "../fleet/sync";
import { startMissions } from "../fleet/mload";
import { select } from "../fleet/actions";
import { pickNode } from "../session/steer";
import { startOrchestra } from "../orchestra/sync"; // the goal run Live draws: the live one, else the newest
import { FleetEdges } from "../agents/live/FleetEdges";
import { LiveBar } from "../agents/live/LiveBar";
import { MachineBox, MachineNode } from "../agents/live/MachineNode";
import { PartEdges, PartNode } from "../agents/live/MissionParts";
import { NodeMenu, type MenuAt } from "../agents/live/NodeMenu";
import { SessionNode } from "../agents/live/SessionNode";
import { ThumbBar } from "../agents/live/ThumbBar";
import { clearPick, pickLive, toggleScope, useLiveScope, useLivePick } from "../agents/live/scope";
import { useLiveNodes } from "../agents/live/useLiveNodes";
import { RunNodeCard } from "../agents/live/runLanes";
import { GroupBar, GroupBox, GroupEdges } from "../agents/live/GroupBox"; // 3.3.16.3: Live in groups
import { useClosed } from "../agents/live/groupStore";
import type { LiveBox } from "./liveLayout";
import { useLiveGeo } from "../agents/live/liveGeo"; // 3.3.18.0: laid out on the tree's shape, painted on its state
import { LiveEmpty, ReplayBanner } from "../agents/live/LiveEmpty"; // 3.3.18.0: nothing runs; a replay from History
import { HistoryDrawer } from "../agents/live/History";
import { Scrubber } from "../agents/live/Scrubber"; // 3.4.1.0 R1 "Time": the one replay control, under the canvas
import { replayDoor } from "../agents/live/replay";
import { GoalDrawer } from "../agents/run/GoalDrawer"; // 3.4.0.0 D: Run a goal, a panel beside the canvas
import { useLivePlan } from "../agents/live/useLivePlan"; // 3.3.18.0 part 2: the plan under it
import { PlanWorld } from "../agents/live/PlanWorld";
import { LiveNow } from "../agents/live/LiveNow"; // 3.3.18.0 part 3: the one sentence, the waits, the waiting path
import { WAITS_H } from "../agents/live/WaitsRow";
import { usePathIds } from "../agents/live/useWaits";
import { fitZoom, levelOf, NEAR_H, setLevel, usePinnedLevel } from "../agents/live/levels"; // 3.3.18.0 part 4: zoom that changes meaning
import { LevelSwitch } from "../agents/live/LevelSwitch";
import { useZoomAnchor } from "../agents/live/zoomAnchor";
import { NAV_HELP, READABLE, recallZoom, useCanvasNav } from "../../lib/canvasNav"; // 3.4.1.3: zoom and pan, the same everywhere
import { ZoomButtons } from "../../lib/ui/ZoomButtons";
import { selectLive } from "./liveModel";
import { LiveGroupBox, LiveNodeCard } from "./LiveNode";
import { useRoles } from "./store";

const LIVE = ["queued", "running", "waiting", "paused"];
const MOTION: Record<string, string> = { working: "working", waiting: "waiting", done: "done", failed: "error" }; // lib/motion's words

function Edges({ boxes, w, h, sel }: { boxes: LiveBox[]; w: number; h: number; sel: string }) {
  const path = usePathIds(); // 3.3.18.0 part 3: the waiting path's hairline
  return (
    <svg className="rlm-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      {boxes.filter((b) => b.d).map((b) => [
        <path key={b.node.id} className="rlm-edge" d={b.d} data-testid="roles-live-edge" data-from={b.from || undefined} data-to={b.node.id}
              data-glow={b.node.glow || undefined} data-motion={MOTION[b.node.glow] || undefined} data-on={(b.node.key && b.node.key === sel) || undefined}
              data-path={(path.includes(b.node.id) && !!b.from && path.includes(b.from)) || undefined} />,
        // 3.3.15.0 L1 (styles/nodes.css): a working child's edge carries a dash moving toward it
        b.node.glow === "working" && <path key={b.node.id + "~flow"} className="rlm-edge-flow" d={b.d} />,
      ])}
    </svg>
  );
}

export function LiveMap({ thumb = false }: { thumb?: boolean }) {
  useEffect(() => startFleet(), []);
  useEffect(() => (thumb ? undefined : (startOrchestra(), startMissions(), replayDoor())), [thumb]); // the newest run of this repo, the missions; `?replay=`
  const scope = useLiveScope();
  const mode = thumb ? "thumb" : scope;
  const { nodes, sid, refs, now, replay, rec } = useLiveNodes(mode);
  const density = useRoles((s) => s.liveDensity);
  const selected = useFleet((s) => s.selected);
  const loaded = useFleet((s) => s.loaded);
  const pick = useLivePick();
  const closed = useClosed();
  const navId = `${thumb ? "map" : "live"}|${scope}`;
  const [zoom, setZoom] = useState(() => recallZoom(navId) ?? 1);
  const manual = useRef(recallZoom(navId) !== undefined); // the person zoomed: the Map's refit on a resize leaves it
  const pinned = usePinnedLevel();
  const level = thumb ? "mid" : pinned || levelOf(zoom); // 3.3.18.0 part 4: far | mid | near by the zoom (levels.ts; `?level=` pins it)
  useEffect(() => void (!thumb && setLevel(level)), [thumb, level]);
  const tree = useLiveGeo(nodes, thumb ? "compact" : density, closed, thumb ? 0 : WAITS_H + (level === "near" ? NEAR_H : 0));
  const plan = useLivePlan(thumb ? "thumb" : mode, nodes, rec, density, replay, level);
  const geo = plan.geo || tree;
  const [menu, setMenu] = useState<MenuAt | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const anchorAt = useZoomAnchor(scroll, zoom, `${level}|${geo.width}x${geo.height}`, setZoom);
  const zoomAt = (z: number, px?: number, py?: number) => ((manual.current = true), anchorAt(z, px, py));
  const fit = () => {
    const el = scroll.current;
    if (!el) return;
    if (thumb) { // 3.4.1.3: fit to the panel, never below the size its text reads at: then the main agent, centred
      const all = Math.min(1, (el.clientWidth - 24) / geo.width, (el.clientHeight - 24) / geo.height);
      if (all >= READABLE) return setZoom(all);
      const main = tree.boxes.find((b) => !b.from) || tree.boxes[0];
      setZoom(READABLE);
      if (main) requestAnimationFrame(() => el.scrollTo((main.x + main.w / 2) * READABLE - el.clientWidth / 2, (main.y + main.h / 2) * READABLE - el.clientHeight / 2));
      return;
    }
    const mid = level === "far" ? (plan.on ? plan.midOf() : null) || tree : geo, far = plan.farOf() || mid; // part 4: Fit picks the level
    if (pinned) return setZoom(Math.max(0.25, Math.min(1.25, (el.clientWidth - 24) / geo.width, (el.clientHeight - 24) / geo.height))); // a pinned level: a plain fit
    setZoom(fitZoom(el.clientWidth, el.clientHeight, mid.width, mid.height, far.width, far.height));
  };
  useAutoFit(scroll, thumb, `${mode}|${sid}|${density}`, nodes.length, geo, () => { if (!manual.current) fit(); }, setZoom);
  useCanvasNav(scroll, { zoom, zoomAt, fit: () => ((manual.current = false), fit()), id: navId });
  const more = thumb && zoom > 0 && (geo.width * zoom > (scroll.current?.clientWidth || 1e9) + 2 || geo.height * zoom > (scroll.current?.clientHeight || 1e9) + 2);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.ctrlKey || e.metaKey || e.altKey || thumb) return;
    if (e.key === "f" && !e.shiftKey) fit();
    else if (e.key === "F") toggleScope(); // 3.3.16.0 R2: this halo | fleet
    else return;
    e.preventDefault();
  };
  const onAgent = thumb ? pickNode : (key: string) => (key.startsWith("replay|") ? undefined : (selectLive(key), pickLive("agent", key))); // a replay's box is not a live agent
  const onSession = thumb ? select : onAgent;
  const agents = nodes.filter((n) => !n.virtual && !n.run && !n.kind);
  const machines = nodes.filter((n) => n.kind === "machine").length;
  const live = agents.filter((n) => LIVE.includes(n.state)).length;
  const empty = !nodes.length || (thumb ? mode === "here" && !agents.length && !nodes.some((n) => n.run) : !agents.length && !nodes.some((n) => n.run || n.kind === "part"));
  return (
    <div className="rc rlm" data-testid="roles-live-map" data-session={mode === "here" ? sid || undefined : undefined} data-scope={mode} data-nodes={agents.length}
         data-machines={machines} data-density={density} data-replay={replay || undefined}>
      {thumb ? <ThumbBar sid={sid} agents={agents.length} live={live} /> : <LiveBar refs={refs} sid={sid} agents={agents.length} live={live} machines={machines} zoom={zoom} setZoom={zoomAt} fit={fit} empty={empty && loaded} plan={plan}
                                                    levels={<LevelSwitch level={level} zoomAt={zoomAt} />} />}
      {!thumb && <ReplayBanner />}
      <LiveNow nodes={nodes} now={now} on={!thumb} plan={plan.geo} />
      {thumb && <div className="cz-thumb"><ZoomButtons zoom={zoom} zoomAt={zoomAt} fit={() => ((manual.current = false), fit())} />
        {more && <span className="cz-more mono muted" data-testid="map-more" title={NAV_HELP}>more than shows: Fit shows all</span>}</div>}
      <div className="rc-scroll rlm-scroll holo-grid" ref={scroll} tabIndex={0} onKeyDown={onKey} aria-label="Agents Live: the agent tree"
           onClick={(e) => !thumb && e.target === e.currentTarget && clearPick()}>
        {!loaded ? (
          <div className="og-wait mono muted">reading the sessions...</div>
        ) : empty && !thumb && !machines ? (
          <LiveEmpty />
        ) : empty && thumb ? (
          <Empty title="No session to draw" testid="roles-live-empty"
                 body="Live draws a running session's agents as they spawn. Start one in a terminal (halo), or from Session: New session (no terminal needed); it appears here the moment it registers." />
        ) : (
          <>{empty && <LiveEmpty compact />}<div className="rc-world" style={{ width: geo.width * zoom, height: geo.height * zoom }} onClick={(e) => !thumb && e.target === e.currentTarget && clearPick()}>
            <div className="rc-inner rlm-inner" style={{ width: geo.width, height: geo.height, transform: `scale(${zoom})` }} data-testid="roles-live-world" data-zoom={zoom.toFixed(3)} data-plan={plan.on ? "on" : undefined} data-level={level}>
              {plan.geo ? <PlanWorld geo={plan.geo} now={now} selected={selected} onMenu={setMenu} onPick={onAgent} /> : (<>
              {tree.machines.map((g) => <MachineBox key={g.card} g={g} label={thumb} />)}
              {tree.groups.map((g) => <LiveGroupBox key={g.card} g={g} />)}
              {tree.tasks.map((b) => <GroupBox key={b.g.id} b={b} now={now} />)}
              <GroupEdges boxes={tree.tasks} w={tree.width} h={tree.height} />
              <Edges boxes={tree.boxes} w={tree.width} h={tree.height} sel={selected} />
              {mode !== "here" && <FleetEdges boxes={tree.boxes} w={tree.width} h={tree.height} />}
              {mode === "fleet" && <PartEdges boxes={tree.boxes} w={tree.width} h={tree.height} />}
              {tree.boxes.map((b) => {
                const n = b.node;
                if (n.run) return <RunNodeCard key={n.id} b={b} />;
                if (n.kind === "machine") return <MachineNode key={n.id} b={b} now={now} selected={pick.kind === "machine" && pick.id === n.harness} onPick={(h) => pickLive("machine", h)} />;
                if (n.kind === "session") return <SessionNode key={n.id} b={b} selected={!!n.key && n.key === selected} onPick={onSession} onMenu={setMenu} hover={!thumb} />;
                if (n.kind === "part") return <PartNode key={n.id} b={b} machines={tree.machines} zoom={zoom} />;
                return <LiveNodeCard key={n.id} b={b} selected={!!n.key && n.key === selected} now={now} onMenu={setMenu} onPick={onAgent} hover={!thumb && !replay} waits={!thumb} />;
              })}
              {tree.tasks.map((b) => <GroupBar key={b.g.id} b={b} now={now} hover={!thumb} />)}
              </>)}
            </div>
          </div></>
        )}
      </div>
      {!thumb && (replay || (mode === "here" && !!sid && !empty)) && <Scrubber sid={sid} title={refs.find((r) => r.id === sid)?.title || ""} lineup={plan.lineup}
                                                                         started={firstStart(nodes)} />}
      {!thumb && <HistoryDrawer />}
      {!thumb && <GoalDrawer />}
      {menu && <NodeMenu at={menu} onClose={() => setMenu(null)} />}
    </div>
  );
}

const firstStart = (nodes: { started: number | null }[]): number | null => {
  const t = Math.min(...nodes.map((n) => n.started || Infinity));
  return isFinite(t) ? t : null;
};

/** The first draw of a tree (a scope, session or density change) fits one bigger than the page; the thumbnail always fits.
 *  A layout effect: the new tree is never painted at the old one's zoom (fleet -> this halo showed the fleet's zoom for
 *  a frame, and a + pressed in that frame was overwritten by the late fit, so Fit seemed to do nothing). */
function useAutoFit(scroll: RefObject<HTMLDivElement | null>, thumb: boolean, shape: string, count: number, geo: { width: number; height: number },
                    fit: () => void, setZoom: (z: number) => void): void {
  const fitted = useRef("");
  useLayoutEffect(() => {
    const el = scroll.current;
    if (!el || !count) return;
    if (thumb) return fit();
    if (fitted.current === shape) return;
    fitted.current = shape;
    if (geo.width > el.clientWidth || geo.height > el.clientHeight) fit();
    else setZoom(1);
  }, [shape, count, geo.width, geo.height]);
  useEffect(() => {
    const el = scroll.current;
    if (!el || !thumb) return;
    const ro = new ResizeObserver(() => fit());
    ro.observe(el);
    return () => ro.disconnect();
  }, [thumb, geo.width, geo.height]);
}
