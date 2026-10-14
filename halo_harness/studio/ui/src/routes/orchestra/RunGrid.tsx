// RunGrid: one tile per lane (5 to 50), coloured by its state, with the
// counters row (joined / writing / in review / waiting / merged). A tile
// that is writing flows, a waiting one pulses amber. Click a tile to focus
// that lane in Lanes and LiveFile.
import type { MotionState } from "../../lib/motion";
import { NoRun } from "./bits";
import { counters, focusLane, LANE_LABEL, laneColor, laneMotion, laneSlots, NONE, useOrch } from "./store";

function Counters() {
  const lanes = useOrch((s) => s.data?.lanes || NONE);
  const c = counters(lanes);
  const cells: [string, number, string][] = [
    ["joined", c.joined, ""],
    ["writing", c.writing, "accent"],
    ["in review", c.review, ""],
    ["waiting", c.waiting, "warn"],
    ["merged", c.merged, "ok"],
  ];
  return (
    <div className="og-counters">
      {cells.map(([label, n, tone]) => (
        <div key={label} className="og-counter" data-tone={tone || undefined} data-zero={n === 0 || undefined}>
          <span className="og-counter-n mono">{n}</span>
          <span className="og-counter-label">{label}</span>
        </div>
      ))}
    </div>
  );
}

function Tiles({ big }: { big?: boolean }) {
  const data = useOrch((s) => s.data);
  const focus = useOrch((s) => s.focusLane);
  const slots = laneSlots(data);
  const dense = slots.length > 20;
  return (
    <div className="og-tiles" data-dense={dense || undefined} data-big={big || undefined}>
      {slots.map(({ n, lane, step }) => {
        const state = lane?.state || (step === "skipped" ? "skipped" : "");
        return (
          <button
            key={n}
            className="og-tile"
            data-testid="grid-tile"
            data-lc={laneColor(n)}
            data-state={state || "pending"}
            data-motion={lane ? laneMotion(lane.state) : "none"}
            data-focus={focus === n || undefined}
            onClick={() => focusLane(focus === n ? null : n)}
            title={`lane ${n}: ${LANE_LABEL[lane?.state || ""] || state}${lane?.title ? " · " + lane.title : ""}${lane?.pieces_returned ? ` · sent back ${lane.pieces_returned}x` : ""}`}
          >
            <span className="og-tile-n mono">{n}</span>
            {!dense && <span className="og-tile-state">{LANE_LABEL[lane?.state || ""] || state}</span>}
            {big && lane?.title && <span className="og-tile-title">{lane.title}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function RunGridGlance() {
  const has = useOrch((s) => !!s.data);
  if (!has) return <NoRun what="The run grid" />;
  return (
    <div className="glance og-grid">
      <Counters />
      <Tiles />
    </div>
  );
}

export function RunGridDetail() {
  const has = useOrch((s) => !!s.data);
  if (!has) return <NoRun what="The run grid" />;
  return (
    <div className="og-grid">
      <Counters />
      <Tiles big />
    </div>
  );
}

export function useGridMotion(): MotionState {
  const lanes = useOrch((s) => s.data?.lanes);
  if (!lanes || !lanes.length) return "none";
  if (lanes.some((l) => l.state === "waiting")) return "waiting";
  return lanes.some((l) => l.state === "writing" || l.state === "in_review") ? "working" : "idle";
}
