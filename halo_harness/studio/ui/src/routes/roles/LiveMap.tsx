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
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { Empty } from "../../lib/ui";
import { useFleet } from "../fleet/store";
import { startFleet } from "../fleet/sync";
import { startMissions } from "../fleet/mload";
import { select } from "../fleet/actions";
import { pickNode } from "../session/steer";
import { startOrchestra } from "../orchestra/sync";
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
import { liveLayout, type LiveBox } from "./liveLayout";
import { selectLive } from "./liveModel";
import { LiveGroupBox, LiveNodeCard } from "./LiveNode";
import { useRoles } from "./store";

const LIVE = ["queued", "running", "waiting", "paused"];
const MOTION: Record<string, string> = { working: "working", waiting: "waiting", done: "done", failed: "error" }; // lib/motion's words

function Edges({ boxes, w, h, sel }: { boxes: LiveBox[]; w: number; h: number; sel: string }) {
  return (
    <svg className="rlm-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      {boxes.filter((b) => b.d).map((b) => [
        <path key={b.node.id} className="rlm-edge" d={b.d} data-testid="roles-live-edge" data-from={b.from || undefined} data-to={b.node.id}
              data-glow={b.node.glow || undefined} data-motion={MOTION[b.node.glow] || undefined} data-on={(b.node.key && b.node.key === sel) || undefined} />,
        // 3.3.15.0 L1 (styles/nodes.css): a working child's edge carries a dash moving toward it
        b.node.glow === "working" && <path key={b.node.id + "~flow"} className="rlm-edge-flow" d={b.d} />,
      ])}
    </svg>
  );
}

export function LiveMap({ thumb = false }: { thumb?: boolean }) {
  useEffect(() => startFleet(), []);
  useEffect(() => (thumb ? undefined : (startOrchestra(), startMissions())), [thumb]); // the newest run of this repo, the missions
  const scope = useLiveScope();
  const mode = thumb ? "thumb" : scope;
  const { nodes, sid, refs, now } = useLiveNodes(mode);
  const density = useRoles((s) => s.liveDensity);
  const selected = useFleet((s) => s.selected);
  const loaded = useFleet((s) => s.loaded);
  const pick = useLivePick();
  const closed = useClosed();
  const geo = useMemo(() => liveLayout(nodes, thumb ? "compact" : density, new Set(closed)), [nodes, density, thumb, closed]);
  const [zoom, setZoom] = useState(1);
  const [menu, setMenu] = useState<MenuAt | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const fit = () => {
    const el = scroll.current;
    if (el) setZoom(Math.max(thumb ? 0.2 : 0.25, Math.min(thumb ? 1 : 1.25, (el.clientWidth - 24) / geo.width, (el.clientHeight - 24) / geo.height)));
  };
  useAutoFit(scroll, thumb, `${mode}|${sid}|${density}`, nodes.length, geo, fit, setZoom);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.ctrlKey || e.metaKey || e.altKey || thumb) return;
    if (e.key === "f" && !e.shiftKey) fit();
    else if (e.key === "F") toggleScope(); // 3.3.16.0 R2: this halo | fleet
    else if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(2, z * 1.2));
    else if (e.key === "-") setZoom((z) => Math.max(0.25, z / 1.2));
    else return;
    e.preventDefault();
  };
  const onAgent = thumb ? pickNode : (key: string) => (selectLive(key), pickLive("agent", key));
  const onSession = thumb ? select : onAgent;
  const agents = nodes.filter((n) => !n.virtual && !n.run && !n.kind);
  const machines = nodes.filter((n) => n.kind === "machine").length;
  const live = agents.filter((n) => LIVE.includes(n.state)).length;
  const empty = !nodes.length || (mode === "here" && !agents.length && !nodes.some((n) => n.run));
  return (
    <div className="rc rlm" data-testid="roles-live-map" data-session={mode === "here" ? sid || undefined : undefined} data-scope={mode} data-nodes={agents.length}
         data-machines={machines} data-density={density}>
      {thumb ? <ThumbBar sid={sid} agents={agents.length} live={live} /> : <LiveBar refs={refs} sid={sid} agents={agents.length} live={live} machines={machines} zoom={zoom} setZoom={setZoom} fit={fit} />}
      <div className="rc-scroll rlm-scroll holo-grid" ref={scroll} tabIndex={0} onKeyDown={onKey} aria-label="Agents Live: the agent tree"
           onClick={(e) => !thumb && e.target === e.currentTarget && clearPick()}>
        {!loaded ? (
          <div className="og-wait mono muted">reading the sessions...</div>
        ) : empty ? (
          <Empty title="No session to draw" testid="roles-live-empty"
                 body="Live draws a running session's agents as they spawn. Start one in a terminal (halo), or from Session: New session (no terminal needed); it appears here the moment it registers." />
        ) : (
          <div className="rc-world" style={{ width: geo.width * zoom, height: geo.height * zoom }} onClick={(e) => !thumb && e.target === e.currentTarget && clearPick()}>
            <div className="rc-inner rlm-inner" style={{ width: geo.width, height: geo.height, transform: `scale(${zoom})` }} data-testid="roles-live-world" data-zoom={zoom.toFixed(2)}>
              {geo.machines.map((g) => <MachineBox key={g.card} g={g} label={thumb} />)}
              {geo.groups.map((g) => <LiveGroupBox key={g.card} g={g} />)}
              {geo.tasks.map((b) => <GroupBox key={b.g.id} b={b} now={now} />)}
              <GroupEdges boxes={geo.tasks} w={geo.width} h={geo.height} />
              <Edges boxes={geo.boxes} w={geo.width} h={geo.height} sel={selected} />
              {mode !== "here" && <FleetEdges boxes={geo.boxes} w={geo.width} h={geo.height} />}
              {mode === "fleet" && <PartEdges boxes={geo.boxes} w={geo.width} h={geo.height} />}
              {geo.boxes.map((b) => {
                const n = b.node;
                if (n.run) return <RunNodeCard key={n.id} b={b} />;
                if (n.kind === "machine") return <MachineNode key={n.id} b={b} now={now} selected={pick.kind === "machine" && pick.id === n.harness} onPick={(h) => pickLive("machine", h)} />;
                if (n.kind === "session") return <SessionNode key={n.id} b={b} selected={!!n.key && n.key === selected} onPick={onSession} onMenu={setMenu} hover={!thumb} />;
                if (n.kind === "part") return <PartNode key={n.id} b={b} machines={geo.machines} zoom={zoom} />;
                return <LiveNodeCard key={n.id} b={b} selected={!!n.key && n.key === selected} now={now} onMenu={setMenu} onPick={onAgent} hover={!thumb} />;
              })}
              {geo.tasks.map((b) => <GroupBar key={b.g.id} b={b} now={now} hover={!thumb} />)}
            </div>
          </div>
        )}
      </div>
      {menu && <NodeMenu at={menu} onClose={() => setMenu(null)} />}
    </div>
  );
}

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
