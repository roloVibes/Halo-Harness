// A square's agent on the Live tree (3.3.16.0 R3, workflows/receipts.py): one row, in place of what the agent does now --
// the square's name in mono, its engine's lane colour on the row's edge, its own cost beside the session's. One fact per
// row, CSS ellipsis (the full text in the tooltip), nothing cut by a character count.
import { cost } from "../../orchestra/format";
import { findAgent, useFleet } from "../../fleet/store";
import type { LiveNode } from "../../roles/liveModel";

export function SquareRow({ n }: { n: LiveNode }) {
  const session = useFleet((s) => Number((n.key && findAgent(s, n.key)?.s.cost_usd) || 0));
  const own = Number(n.cost) || 0;
  const text = `square ${n.square} · ${n.engine || "session"} · ${cost(own)} of session ${cost(session)}`;
  return (
    <div className="mono rlm-line rlm-square" data-testid="roles-live-square-row" data-engine={n.engine || "session"} title={text}>
      <b data-testid="roles-live-square">{n.square}</b>
      <span className="muted"> · {n.engine || "session"} · </span>
      <span className="rlm-square-cost">{cost(own)}</span>
      <span className="muted" data-testid="roles-live-session-cost"> of session {cost(session)}</span>
    </div>
  );
}
