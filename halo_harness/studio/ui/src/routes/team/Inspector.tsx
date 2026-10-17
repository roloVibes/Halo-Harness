// team-inspector (3.0.8.0 R2): one of three faces by what the board has
// selected -- a stage (its row, Run, the gate card), a block (holders and
// changes) or a member (lineup, role, harness, its stages). With nothing
// selected: the stage that waits on you first, else a line on what to click.
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { BlockFace, MemberFace } from "./InspectorBlock";
import { StageFace } from "./InspectorStage";
import { gatedRows, useTeam } from "./store";

export function InspectorDetail() {
  const sel = useTeam((s) => s.sel);
  const waiting = useTeam((s) => gatedRows(s)[0]?.id || "");
  const pick = sel || (waiting ? { kind: "stage" as const, id: waiting } : null);
  return (
    <div className="tm-inspector" data-testid="team-inspector-body" data-face={pick?.kind || "none"}>
      {!pick ? (
        <div className="tm-face">
          <p className="muted">Click a stage on the board for its row, Run and its gate; a block for who holds it and what changed; a member for its lineup and stages.</p>
        </div>
      ) : pick.kind === "stage" ? (
        <StageFace id={pick.id} />
      ) : pick.kind === "block" ? (
        <BlockFace id={pick.id} />
      ) : (
        <MemberFace name={pick.id} />
      )}
    </div>
  );
}

export function InspectorGlance() {
  const sel = useTeam((s) => s.sel);
  const gated = useTeam((s) => gatedRows(s).length);
  return (
    <div className="glance">
      <div className="glance-kicker mono">{sel ? sel.kind.toUpperCase() : "NOTHING SELECTED"}</div>
      <div className="glance-text">{sel ? sel.id : "Click the board"}</div>
      <div className="glance-numbers">
        <Metric value={gated} label="at a gate" tone={gated ? "warn" : undefined} />
      </div>
    </div>
  );
}

export function useInspectorMotion(): MotionState {
  return useTeam((s) => (gatedRows(s).length ? "waiting" : s.sel ? "idle" : "none"));
}
