// Roles Live (3.3.11.0 R2; rolo 2026-11-02: "the roles tab kept up with what's happening during sessions for
// better map views"): the Canvas panel's Live face, the session's actual agent tree on the whole canvas -- one
// node per agent the work record holds (lib/work/record.ts: live, or finished and still in the frames), parent
// -> child edges, nothing dropped (liveModel.ts), each lineup card the agents match as a faint group behind them,
// an `auto` pick's reason on its node, laid out in layers (liveLayout.ts over the Map's layoutTree.ts) with zoom
// and Fit. A click selects the agent and the Inspector's Live tab follows it (as the Map's click); a node's
// "steer" chip and "..." menu are the Map's. The session picker lists every session the fleet frames carry
// (this harness first, the newest first). Plan | Live on the bar (L toggles it, J / K hop the working agents).
// 3.3.16.0 R1 (Agents -> Live): a live Orchestra run joins the tree -- its lead, each lane under it with its number in
// the lane colour and its worktree (routes/agents/live/runLanes.tsx); the counts stay the session's agents.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Empty } from "../../lib/ui";
import { recordRefs, useSessionRecord } from "../../lib/work/record";
import { NodeMenu, type MenuAt } from "../fleet/MapNode";
import { fleet, useFleet, useNow, type FleetState } from "../fleet/store";
import { startFleet } from "../fleet/sync";
import { liveLayout } from "./liveLayout";
import { liveNodes, liveSession } from "./liveModel";
import { LiveBar, LiveGroupBox, LiveNodeCard } from "./LiveNode";
import { useRoles } from "./store";
import { RunNodeCard, runNodes } from "../agents/live/runLanes";
import { useOrch } from "../orchestra/store";
import { startOrchestra } from "../orchestra/sync";

const LIVE = ["queued", "running", "waiting", "paused"];

function Edges({ boxes, w, h, sel }: { boxes: ReturnType<typeof liveLayout>["boxes"]; w: number; h: number; sel: string }) {
  return (
    <svg className="rlm-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      {boxes.filter((b) => b.d).map((b) => [
        <path key={b.node.id} className="rlm-edge" d={b.d} data-testid="roles-live-edge" data-from={b.from || undefined} data-to={b.node.id}
              data-glow={b.node.glow || undefined} data-on={(b.node.key && b.node.key === sel) || undefined} />,
        // 3.3.15.0 L1 (styles/nodes.css): a working child's edge carries a dash moving toward it
        b.node.glow === "working" && <path key={b.node.id + "~flow"} className="rlm-edge-flow" d={b.d} />,
      ])}
    </svg>
  );
}

export function LiveMap() {
  useEffect(() => startFleet(), []);
  useEffect(() => startOrchestra(), []); // the newest run of this repo: drawn while it is live
  const run = useOrch((s) => s.data);
  const want = useRoles((s) => s.liveSid);
  const density = useRoles((s) => s.liveDensity);
  const graph = useRoles((s) => s.graph);
  const lineup = useRoles((s) => s.name);
  const harnesses = useFleet((s) => s.harnesses);
  const activity = useFleet((s) => s.activity);
  const selected = useFleet((s) => s.selected);
  const loaded = useFleet((s) => s.loaded);
  const now = useNow(true, 1000);
  const refs = useMemo(() => recordRefs({ harnesses } as FleetState), [harnesses]);
  const sid = useMemo(() => liveSession({ harnesses } as FleetState, want), [harnesses, want]);
  const rec = useSessionRecord(sid);
  const lanes = useMemo(() => runNodes(run), [run]);
  const nodes = useMemo(() => [...(rec ? liveNodes(rec, fleet.get(), graph?.nodes || [], lineup, now) : []), ...lanes], [rec, graph, lineup, activity, now, lanes]);
  const geo = useMemo(() => liveLayout(nodes, density), [nodes, density]);
  const [zoom, setZoom] = useState(1);
  const [menu, setMenu] = useState<MenuAt | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const fit = () => {
    const el = scroll.current;
    if (el) setZoom(Math.max(0.25, Math.min(1.25, (el.clientWidth - 24) / geo.width, (el.clientHeight - 24) / geo.height)));
  };
  const fitted = useRef("");
  useEffect(() => {
    // the first draw of a session (and a density change) fits a tree bigger than the page
    const el = scroll.current;
    const shape = `${sid}|${density}`;
    if (!el || !nodes.length || fitted.current === shape) return;
    fitted.current = shape;
    if (geo.width > el.clientWidth || geo.height > el.clientHeight) fit();
    else setZoom(1);
  }, [sid, density, nodes.length, geo.width, geo.height]);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "f" && !e.shiftKey) fit();
    else if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(2, z * 1.2));
    else if (e.key === "-") setZoom((z) => Math.max(0.25, z / 1.2));
    else return;
    e.preventDefault();
  };
  const agents = nodes.filter((n) => !n.virtual && !n.run);
  return (
    <div className="rc rlm" data-testid="roles-live-map" data-session={sid || undefined} data-nodes={agents.length} data-density={density}>
      <LiveBar refs={refs} sid={sid} agents={agents.length} live={agents.filter((n) => LIVE.includes(n.state)).length} zoom={zoom} setZoom={setZoom} fit={fit} />
      <div className="rc-scroll rlm-scroll holo-grid" ref={scroll} tabIndex={0} onKeyDown={onKey} aria-label="Roles Live: the session's agent tree">
        {!loaded ? (
          <div className="og-wait mono muted">reading the sessions...</div>
        ) : !rec && !lanes.length ? (
          <Empty title="No session to draw" testid="roles-live-empty"
                 body="Live draws a running session's agents as they spawn. Start one in a terminal (halo), or from Session: New session (no terminal needed); it appears here the moment it registers." />
        ) : (
          <div className="rc-world" style={{ width: geo.width * zoom, height: geo.height * zoom }}>
            <div className="rc-inner rlm-inner" style={{ width: geo.width, height: geo.height, transform: `scale(${zoom})` }} data-testid="roles-live-world" data-zoom={zoom.toFixed(2)}>
              {geo.groups.map((g) => <LiveGroupBox key={g.card} g={g} />)}
              <Edges boxes={geo.boxes} w={geo.width} h={geo.height} sel={selected} />
              {geo.boxes.map((b) => (b.node.run ? <RunNodeCard key={b.node.id} b={b} />
                : <LiveNodeCard key={b.node.id} b={b} selected={!!b.node.key && b.node.key === selected} now={now} onMenu={setMenu} />))}
            </div>
          </div>
        )}
      </div>
      {menu && <NodeMenu at={menu} onClose={() => setMenu(null)} />}
    </div>
  );
}
