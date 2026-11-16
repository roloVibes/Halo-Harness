// session-map (3.1.4.0 R2; 3.6.0.0 R4 the lit map; 3.6.0.0 R5: every session runs on a map, the old tree went): the
// session drawn as its map, top to bottom and read-only (MapDown.tsx, 3.6.0.2 R7-R12) -- its boxes, what each does now, the
// helpers it made up -- with a link to Agents -> 3 · Map, where the same map is lit full size. 3.6.0.2 R1: the session
// drawn is `chosenSession` (the one Prompt, Cost and the Feed speak of), held while it is open, never "the first on a
// map"; R2: open = drawn, busy only lights boxes; R4: one that ended reads T8 until another is picked; R5: a Studio
// session with no message yet reads T10 (no drawing, no fetch). Its head line is the truth sentence (truth.ts).
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { useScopedCounts } from "../fleet/scope";
import { useFleet } from "../fleet/store";
import { toLit } from "../crew/map/litStore";
import { truthLines, truthState } from "../crew/map/truth";
import { factsOf, lastRow } from "./pick";
import { MapDown } from "./MapDown";
import { chosenSession } from "./store";

/** The drawer's one line when it draws nothing (T8, T10): the truth sentence, its state and session. */
function Said({ sid, state, text }: { sid: string; state: string; text: string }) {
  return <p className="cw-line" data-testid="session-lit-line" data-state={state} data-sid={sid}>{text}</p>;
}

export function MapDetail() {
  const loaded = useFleet((s) => s.loaded);
  const error = useFleet((s) => s.error);
  const any = useFleet((s) => s.harnesses.length);
  const row = useFleet(chosenSession);
  const pick = useFleet((s) => s.scope.session || "");
  if (!loaded) return null; // the section's own wait says it while it reads
  if (error && !any) return <Empty title="Studio could not read the sessions" body={error} />;
  const ended = !row && pick ? lastRow(pick) : null;
  if (ended) {
    const f = factsOf(ended.row, ended.ended);
    return <Said sid={pick} state={truthState(f)} text={truthLines(f).map((l) => l.text).join(" ")} />;
  }
  if (!row) return <Empty title="No session is running here" body="Start one (Session's prompt, or halo in a terminal): it is drawn here as its map." />;
  const f = factsOf(row);
  const line = truthLines(f).map((l) => l.text).join(" ");
  if (truthState(f) === "T10") return <Said sid={row.session_id} state="T10" text={line} />;
  return <MapDown key={row.session_id} s={toLit(row)} line={line} state={truthState(f)} />;
}

export function MapGlance() {
  const c = useScopedCounts();
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={c.sessions} label="sessions" />
        <Metric value={c.live} label="agents live" tone="accent" />
        <Metric value={c.attention} label="need you" tone={c.attention ? "warn" : undefined} />
      </div>
      <div className="glance-hint">Expand for the map: the session running here, its boxes and helpers.</div>
    </div>
  );
}

export function useMapMotion(): MotionState {
  const c = useScopedCounts();
  const error = useFleet((s) => !!s.error);
  if (error) return "error";
  if (c.attention) return "waiting";
  return c.live ? "working" : c.harnesses ? "idle" : "none";
}
