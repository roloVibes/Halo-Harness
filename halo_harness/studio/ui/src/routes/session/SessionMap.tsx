// session-map, Session's Live drawer (3.6.0.2 R35: titled Live; 3.1.4.0 R2; 3.6.0.0 R4 the lit map; 3.6.0.0 R5: every session runs on a map, the old tree went): the
// session drawn as its map, top to bottom and read-only (MapDown.tsx, 3.6.0.2 R7-R12) -- its boxes, what each does now, the
// helpers it made up -- with a link to Agents -> 3 · Map, where the same map is lit full size. 3.6.0.2 R1: the session
// drawn is `chosenSession` (the one Prompt, Cost and the Feed speak of), held while it is open, never "the first on a
// map"; R2: open = drawn, busy only lights boxes; R4: one that ended reads T8 until another is picked; R5: a Studio
// session with no message yet reads T10 (no drawing, no fetch); no session at all reads Empty. Its head is the truth
// block (TruthBlock.tsx, R20-R23: truth.ts's sentences, the status line).
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { useScopedCounts } from "../fleet/scope";
import { useFleet } from "../fleet/store";
import { toLit } from "../crew/map/litStore";
import { truthState, WORDS, type TruthFacts } from "../crew/map/truth";
import { useNextB } from "./nextB";
import { factsOf, lastRow } from "./pick";
import { MapDown } from "./MapDown";
import { chosenSession } from "./store";
import { TruthBlock } from "./TruthBlock";

/** R4: no session row: the Start view's Empty sentence ({B} as this page last heard it) with [New session]. */
export const noneFacts = (b: string | null): TruthFacts => ({ none: true, title: "", a: null, plain: false, b, bSince: null, started: 0,
  turns: 0, studio: false, ended: null, machine: null, unreadable: null, changed: null, workflow: null, busy: false });

/** R4: Empty's {B} is the server's (nextB.ts: read after the first draw and on a map or config change), never a row's
 *  that ended; until read the block holds its room with no words. */
function EmptyTruth() {
  const b = useNextB();
  return <TruthBlock key="none" f={noneFacts(b ?? null)} sid="" held={b === undefined} />;
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
  if (ended) return <TruthBlock key={pick} f={factsOf(ended.row, ended.ended)} sid={pick} />; // R4: T8 until another is picked
  if (!row) return <EmptyTruth />; // R4: Empty
  const f = factsOf(row);
  if (truthState(f) === "T10") return <TruthBlock key={row.session_id} f={f} sid={row.session_id} />;
  return <MapDown key={row.session_id} s={toLit(row)} f={f} />;
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
      <div className="glance-hint">Expand for {WORDS.live}: the session running here, drawn on the map it runs on.</div>
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
