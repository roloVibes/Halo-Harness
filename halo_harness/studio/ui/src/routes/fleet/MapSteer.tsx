// The "steer" chip of a map node (3.1.7.0 R1): it shows while the pointer is
// on the node (or the node has the keyboard focus) and steers that agent in
// one click: in Session it pins the agent in the Live column and puts the
// keyboard in the column's Steer box; in Fleet it opens the Agent panel's box
// (routes/session/steer.ts `steerAgent`). The node's `...` menu keeps its own
// Steer item. Drawn in SVG at `x, y`, right-aligned to `x`.
import type { MouseEvent } from "react";
import { steerAgent } from "../session/steer";

export const STEER_W = 46;

export function SteerChip({ k, name, x, y }: { k: string; name: string; x: number; y: number }) {
  const go = (e: MouseEvent) => {
    e.stopPropagation();
    steerAgent(k);
  };
  return (
    <g className="fm-steer" data-testid="fleet-node-steer" transform={`translate(${x - STEER_W} ${y})`} role="button" aria-label={`steer ${name}`}
       onClick={go} onDoubleClick={(e) => e.stopPropagation()}>
      <title>{`Steer ${name}: the Steer box, addressed to it`}</title>
      <rect width={STEER_W} height={14} rx={7} />
      <text x={STEER_W / 2} y={10.5} textAnchor="middle">steer ▸</text>
    </g>
  );
}
