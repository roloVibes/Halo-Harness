// Cast is the plan and says so (3.3.18.0 "The living canvas"): one line on its bar -- the lineup new sessions use -- and,
// while agents run, a chip with their count that goes to Live. The cards light only for agents running under them now
// (roles/glow.ts: never from a session that ended).
import { useRoles } from "../../roles/store";
import { setAgentsView } from "../store";
import { useLiveCount } from "./now";

export function CastLine() {
  const used = useRoles((s) => s.info?.active_team || (s.info?.lineup_default ? `${s.info?.lineup_in_use || "auto"} (default)` : ""));
  const loaded = useRoles((s) => s.loaded);
  const n = useLiveCount();
  return (
    <>
      {loaded && (
        <span className="mono muted ag-plan-line" data-testid="cast-plan-line" title="Cast is the plan: the lineup's cards and tiers. What runs now is on Live.">
          the lineup new sessions use: <b className="ag-plan-name">{used || "none (one model for everything)"}</b>
        </span>
      )}
      {n > 0 && (
        <button className="og-chip mono ag-live-chip" onClick={() => setAgentsView("live")} data-testid="cast-live-chip" data-count={n}
                title="Agents at work now: Live draws them (L)">
          {n} live -- see Live
        </button>
      )}
    </>
  );
}
