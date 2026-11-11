// Live with the plan under it, drawn (3.3.18.0 "The living canvas" part 2; useLivePlan.ts says what, planLayout.ts where):
// each block of the lineup -- main, a tier, a square -- as a box with its title bar (a block in use: its name, its
// counts, state and cost, its purpose; one nobody uses: dim, its name and purpose), the live agents inside it as Live's
// own nodes, main's line into each tier and square with the plan's when on it. The line into a block at work carries the
// moving dash (the one motion allowed); every other line is still.
import { useHover } from "../../../lib/hover/useHover";
import { LiveNodeCard } from "../../roles/LiveNode";
import type { MenuAt } from "./NodeMenu";
import { countLine, tally } from "./GroupBox";
import { GroupHover } from "../hover/group";
import type { PlanBox, PlanGeometry } from "./planLayout";
import { RunNodeCard } from "./runLanes";
import { LineLabel } from "./LineLabel"; // part 3: the latest hand-off on a line, its last three exchanges
import { usePathIds } from "./useWaits";
import { FAR_SCALE } from "./levels";

type Props = { geo: PlanGeometry; now: number; selected: string; onMenu: (m: MenuAt) => void; onPick: (key: string) => void };

function Block({ b, now }: { b: PlanBox; now: number }) {
  const t = tally(b, now);
  const hv = useHover("group", `plan:${b.def.id}`, () => <GroupHover b={{ g: { id: b.def.id, title: b.def.title, why: b.def.purpose, kind: "task", parent: null }, members: b.members, by: "", x: 0, y: 0, w: 0, h: 0, head: 0, open: true, depth: 0, from: null, d: "" }} now={now} />, b.used);
  return (
    <>
      <div className="pb-box" style={{ left: b.x, top: b.y, width: b.w, height: b.h }} data-testid="live-block" data-block={b.def.id} data-kind={b.def.kind}
           data-used={b.used || undefined} data-glow={t.glow || undefined} data-asks={t.waiting > 0 || undefined} data-count={t.count} />
      <div className="pb-bar" data-density="bar" style={{ left: b.x, top: b.y, width: b.w, height: b.head }} data-testid="live-block-bar" data-block={b.def.id} data-kind={b.def.kind}
           data-used={b.used || undefined} data-glow={t.glow || undefined} data-asks={t.waiting > 0 || undefined} {...hv.props}>
        <b className="pb-title" data-testid="live-block-title" title={hv.titles ? b.def.title : undefined}>{b.def.title}</b>
        {b.used && <div className="pb-counts mono" data-testid="live-block-counts">{countLine(t)}</div>}
        {b.def.purpose && <div className="pb-purpose mono" data-testid="live-block-purpose" title={b.def.purpose}>{b.def.purpose}</div>}
      </div>
    </>
  );
}

export function PlanWorld({ geo, now, selected, onMenu, onPick }: Props) {
  const working = new Set(geo.blocks.filter((b) => tally(b, now).working > 0).map((b) => b.def.id));
  const path = usePathIds();
  const onPath = new Set(geo.blocks.filter((b) => b.def.id !== "main" && b.members.some((m) => path.includes(m.id))).map((b) => b.def.id));
  const root = geo.boxes.find((b) => !b.node.parent && b.node.key)?.node.key || "";
  return (
    <>
      {geo.blocks.map((b) => <Block key={b.def.id} b={b} now={now} />)}
      <svg className="rlm-edges" width={geo.width} height={geo.height} viewBox={`0 0 ${geo.width} ${geo.height}`} aria-hidden="true">
        {geo.lines.map((l) => [
          <path key={l.to} className="rlm-edge pb-line" d={l.d} data-testid="live-plan-line" data-to={l.to} data-live={working.has(l.to) || undefined}
                data-path={onPath.has(l.to) || undefined} />,
          working.has(l.to) && <path key={l.to + "~flow"} className="rlm-edge-flow" d={l.d} />,
        ])}
      </svg>
      {geo.lines.map((l) => <LineLabel key={l.to} l={l} b={geo.blocks.find((b) => b.def.id === l.to)} root={root} now={now} scale={geo.far ? FAR_SCALE : 1} />)}
      {geo.boxes.map((b) => (b.node.run ? <RunNodeCard key={b.node.id} b={b} />
        : <LiveNodeCard key={b.node.id} b={b} selected={!!b.node.key && b.node.key === selected} now={now} onMenu={onMenu} onPick={onPick} hover />))}
    </>
  );
}
