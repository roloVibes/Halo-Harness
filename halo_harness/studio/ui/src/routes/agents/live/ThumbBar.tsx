// Session's Map bar (3.3.11.0 R2 as the Fleet Map's scoped toolbar; 3.3.16.0 R2: the Map is Live's tree as a
// thumbnail): this harness's counts, the decisions that wait on you here, and "Open in Agents Live" -- the same tree,
// full size, on Agents -> Live (this halo, on the session Session shows).
import { goSection } from "../../../lib/store";
import { useScopedAttention, useScopedCounts } from "../../fleet/scope";
import { useFleet } from "../../fleet/store";
import { openRolesLive } from "../../roles/liveModel";
import { startRoles } from "../../roles/sync";
import { chosenSession } from "../../session/store";

export function ThumbBar({ agents, live }: { sid: string; agents: number; live: number }) {
  const c = useScopedCounts();
  const attn = useScopedAttention().count;
  const sid = useFleet((s) => chosenSession(s)?.session_id || "");
  const go = () => openRolesLive(sid, () => (goSection("agents", "live"), startRoles()));
  return (
    <div className="fm-bar rlm-thumb-bar">
      <span className="mono muted fm-counts">
        this harness · {c.sessions} session{c.sessions === 1 ? "" : "s"} · {live} of {agents} agents live
        {attn > 0 && <b className="fm-attn"> · {attn} need{attn === 1 ? "s" : ""} you</b>}
      </span>
      <span className="spacer" />
      <button className="og-link mono fm-expand" onClick={go} disabled={!sid} title="The same tree, full size: Agents, Live (and back: Session in the rail)"
              data-testid="session-map-expand">Open in Agents Live</button>
    </div>
  );
}
