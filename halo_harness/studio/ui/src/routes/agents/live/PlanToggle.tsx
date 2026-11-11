// "Plan under it" on Live's bar (3.3.18.0 "The living canvas" part 2): on, the lineup's blocks are the map and the live
// agents sit inside the block each belongs to; off, Live is the grouped tree. It shows only when the session's lineup can
// be drawn (this halo's scope, no replay).
import { setPlanOn } from "./planStore";

export function PlanToggle({ on, lineup }: { on: boolean; lineup: string }) {
  return (
    <button className={"btn btn-ghost btn-sm pb-toggle" + (on ? " on" : "")} aria-pressed={on} onClick={() => setPlanOn(!on)} data-testid="live-plan-toggle"
            title={on ? `Plan under it: on. The blocks of ${lineup} are the map, each agent inside its block. A click draws the plain tree.`
              : `Plan under it: off. A click draws ${lineup}'s blocks (main, each tier, each square) with each agent inside its block.`}>
      <span className="btn-label">Plan under it</span>
    </button>
  );
}
