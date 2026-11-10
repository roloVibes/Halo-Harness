// The Live tree's two passing edges (3.3.16.0 R2 "the Fleet fold": the Fleet Map's, folded in): an edge that lights
// for LIT_MS when an agent spawns or messages another (`fleet-lit-edge`, data-kind spawn | message | talk: 3.3.16.2, one
// agent's words to another, drawn from the speaker to the listener with an arrow at the listener), and the amber
// dashed warning edge between two agents of different sessions editing one file (`fleet-conflict-edge`, GET
// fleet/conflicts; its attention row's `o` opens Live on them). Both join the nodes by their fleet keys, on top of the
// tree's own edges.
import { useRecent } from "../../../lib/motion";
import { usePanels } from "../../fleet/pstore";
import { NONE, useFleet } from "../../fleet/store";
import type { LiveBox } from "../../roles/liveLayout";

const LIT_MS = 3000;

type Pos = Map<string, LiveBox>;

/** A curve from `a`'s right edge to `b`'s, bending out to the right (two nodes of one column join on that side). */
function curve(a: LiveBox, b: LiveBox): string {
  const x1 = a.x + a.w - 6, y1 = a.y + a.h / 2, x2 = b.x + b.w - 6, y2 = b.y + b.h / 2;
  const bend = Math.max(28, Math.abs(y2 - y1) / 3, Math.abs(x2 - x1) / 4);
  return `M${x1} ${y1} C${x1 + bend} ${y1} ${x2 + bend} ${y2} ${x2} ${y2}`;
}

function Lit({ pos }: { pos: Pos }) {
  const edges = useFleet((s) => s.edges || NONE);
  const last = edges.length ? edges[edges.length - 1].ts : 0;
  const fresh = useRecent(last, LIT_MS);
  if (!fresh) return null;
  const now = Date.now();
  return (
    <g className="fm-lit-edges">
      {edges.filter((e) => now - e.ts < LIT_MS).map((e) => {
        const a = pos.get(e.from), b = pos.get(e.to);
        return a && b ? <path key={`${e.from}>${e.to}@${e.ts}`} className="fm-edge fm-edge-lit" data-kind={e.kind} data-testid="fleet-lit-edge" d={curve(a, b)}
                              data-from={e.from} data-to={e.to} markerEnd={e.kind === "talk" ? "url(#fm-talk-arrow)" : undefined} /> : null;
      })}
    </g>
  );
}

function Conflicts({ pos }: { pos: Pos }) {
  const list = usePanels((s) => s.conflicts?.conflicts) || NONE;
  return (
    <g className="fm-conflicts">
      {list.map((c) => {
        const a = pos.get(c.a.key), b = pos.get(c.b.key);
        if (!a || !b) return null;
        return (
          <path key={c.id} className="fm-edge fm-edge-conflict" d={curve(a, b)} data-testid="fleet-conflict-edge" data-file={c.file}>
            <title>{`${c.a.name} (${c.a.harness_name}) and ${c.b.name} (${c.b.harness_name}) are both editing ${c.repo}/${c.file}`}</title>
          </path>
        );
      })}
    </g>
  );
}

export function FleetEdges({ boxes, w, h }: { boxes: LiveBox[]; w: number; h: number }) {
  const pos: Pos = new Map(boxes.filter((b) => b.node.key && !b.node.kind).map((b) => [b.node.key, b]));
  return (
    <svg className="rlm-edges rlm-fleet-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <defs>
        <marker id="fm-talk-arrow" className="fm-talk-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 8 4 0 8Z" />
        </marker>
      </defs>
      <Lit pos={pos} />
      <Conflicts pos={pos} />
    </svg>
  );
}
