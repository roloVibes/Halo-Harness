// An agent node of the map drawn as a tree (3.1.5.0 R3, Session's scope;
// layoutTree.ts places it): the state dot and the name, the model pill and
// the running cost, and the third line: while a tool runs its name and how
// long it has run ("Bash 12s", from the feed: shared/liveFeed.ts), else what
// it does now. The selected node carries the HUD brackets; a line hovered in
// the Live column lights its node (data-hover). Motion and colours follow
// the state (fleet.css, holo.css): working a cyan pulse, waiting amber, done
// a green that fades, failed a red that stays. 3.1.7.0 R1: the "steer" chip
// shows on hover (MapSteer.tsx): pin it in Live and steer it there.
// 3.3.0.0 R6: the Steer box's target carries `data-target` (a steady outline,
// its steer chip lit) while Session shows. 3.3.15.0 L1, the Instrument look
// (styles/nodes.css): a 2 px rule across the top in the state colour, a state
// square, the model without its provider prefix (lib/modelName.ts; the full id
// in the tooltip and the Agent panel), a 1 px outline at 3 px when selected or
// hovered elsewhere (a Live line), a node that appears after the page drew
// fades in once (`data-born`), and a failed one keeps its red until clicked
// (`data-ack` after the click).
import { useEffect, type MouseEvent } from "react";
import { useRecent } from "../../lib/motion";
import { ackFailed, failedAcked, useBorn } from "../../lib/motion/born";
import { shortModel } from "../../lib/modelName";
import { Icon, toolIcon } from "../../lib/ui";
import { cost, short } from "../orchestra/format";
import { startLive, useOpenTool } from "../shared/liveFeed";
import { openAgentPanel } from "./actions";
import type { NodeBox } from "./layout";
import { nowText, useTicker, type MenuAt } from "./MapNode";
import { SteerChip } from "./MapSteer";
import { pickNode, useTargetKey } from "../session/steer";
import { agentMotion, DONE_MS, toolOf, useFleet, useNow } from "./store";
import type { AgentRow, Activity } from "./types";

const fit = (text: string, px: number) => short(text, Math.max(4, Math.floor(px / 6.4)));

/** "Bash 12s" while a tool runs (its start seen on the feed), "Bash" when only the row says so, "" when none. */
export function useToolClock(key: string, a: AgentRow, act: Activity | undefined): { tool: string; text: string; secs: number | null } {
  useEffect(() => startLive(), []);
  const open = useOpenTool(key);
  const running = a.state === "running";
  const now = useNow(running && !!open, 1000);
  const tool = running ? open?.tool || toolOf(a, act) : "";
  if (!tool) return { tool: "", text: "", secs: null };
  const secs = open ? Math.max(0, Math.round((now - open.t0) / 1000)) : null;
  const clock = secs == null ? "" : secs < 60 ? ` ${secs}s` : ` ${Math.floor(secs / 60)}m ${String(secs % 60).padStart(2, "0")}s`;
  return { tool, text: tool + clock, secs };
}

export function TreeNode({ n, onMenu, menuOf }: { n: NodeBox; onMenu: (m: MenuAt) => void; menuOf: (e: MouseEvent, key: string) => MenuAt }) {
  const { key, a } = n.ref;
  const selected = useFleet((s) => s.selected === key);
  const hovered = useFleet((s) => s.hover === key);
  const pinned = useFleet((s) => s.pinned === key);
  const target = useTargetKey() === key;
  const doneAt = useFleet((s) => s.doneAt[key] || 0);
  useRecent(doneAt, DONE_MS); // re-draws when the done glow has faded
  const act = useFleet((s) => s.activity[key]);
  const clock = useToolClock(key, a, act);
  const shownCost = useTicker(Number(a.cost_usd) || 0);
  const name = a.name || a.role || a.agent_id;
  const role = a.role && a.role !== name ? a.role : a.bio && a.bio !== name ? a.bio : "";
  const parent = (n.ref.s.agents || []).find((x) => x.agent_id === a.parent);
  const model = shortModel(a.model);
  const pillW = Math.min(n.w - 74, Math.max(40, model.length * 5.9 + 14));
  const [born, grown] = useBorn();
  const failed = a.state === "failed";
  const pick = () => (failed && ackFailed(key), pickNode(key));
  return (
    <g className="fm-node" data-testid="fleet-node" data-tree="" data-key={key} data-state={a.state || "none"} data-motion={agentMotion(a, doneAt)} data-selected={selected || undefined} data-target={target || undefined}
       data-hover={hovered || undefined} data-parent={a.parent || undefined} data-hc={n.hc} data-born={born || undefined} data-ack={(failed && failedAcked(key)) || undefined}
       transform={`translate(${n.x} ${n.y})`} role="button" tabIndex={0} onAnimationEnd={(e) => e.target === e.currentTarget && grown()}
       aria-label={`${name}: ${a.state}`} onClick={pick} onDoubleClick={() => openAgentPanel(key)} onKeyDown={(e) => e.key === "Enter" && openAgentPanel(key)}>
      <title>{`${name}${role ? " (" + role + ")" : ""}: ${a.state}${parent ? "\nspawned by " + (parent.name || parent.role || parent.agent_id) : ""}${a.model ? "\non " + a.model : ""}${a.task ? "\n" + a.task : ""}`}</title>
      {(selected || hovered) && <rect className="fm-ring" data-testid="fleet-node-outline" x={-3.5} y={-3.5} width={n.w + 7} height={n.h + 7} rx={6} />}
      {target && <rect className="fm-target" data-testid="fleet-node-target" x={-3} y={-3} width={n.w + 6} height={n.h + 6} rx={10} />}
      <rect className="fm-shape" width={n.w} height={n.h} rx={4} />
      <rect className="fm-rule" width={n.w} height={2} aria-hidden="true" />
      <rect className="fm-dot" x={9} y={10} width={7} height={7} rx={1} />
      <text className="fm-name" x={22} y={17}>
        {fit(name, n.w - 52 - (role ? 40 : 0))}
        {role && <tspan className="fm-role">{" · " + fit(role, 40)}</tspan>}
      </text>
      {pinned && <g className="fm-pin" transform={`translate(${n.w - 40} 4)`}><Icon name="pin" size={12} /></g>}
      <SteerChip k={key} name={name} x={n.w - (pinned ? 44 : 27)} y={5} />
      <g className="fm-more" transform={`translate(${n.w - 22} 5)`} role="button" aria-label={`${name}: more`}
         onClick={(e) => (e.stopPropagation(), onMenu(menuOf(e, key)))} onDoubleClick={(e) => e.stopPropagation()}>
        <rect width={18} height={14} rx={4} />
        <text x={9} y={10.5} textAnchor="middle">...</text>
      </g>
      {model && (
        <g className="fm-pill" transform="translate(10 24)" data-testid="fleet-node-model">
          <rect width={pillW} height={14} rx={7} />
          <text x={pillW / 2} y={10.5} textAnchor="middle">{fit(model, pillW - 8)}</text>
        </g>
      )}
      <text className="fm-cost" x={n.w - 10} y={35} textAnchor="end" data-testid="fleet-node-cost">{cost(shownCost)}</text>
      {clock.tool ? (
        <g className="fm-tool" data-tool={clock.tool} data-testid="fleet-node-tool" data-secs={clock.secs ?? undefined} transform="translate(10 42)">
          <title>{a.current || clock.tool}</title>
          <Icon name={toolIcon(clock.tool)} size={11} />
          <text className="fm-tool-text" x={15} y={9.5}>{fit(clock.text + (a.current && a.current.includes(":") ? " · " + a.current.split(":").slice(1).join(":").trim() : ""), n.w - 34)}</text>
        </g>
      ) : (
        <text className="fm-now" x={10} y={51}>{fit(nowText(a), n.w - 20)}</text>
      )}
    </g>
  );
}
