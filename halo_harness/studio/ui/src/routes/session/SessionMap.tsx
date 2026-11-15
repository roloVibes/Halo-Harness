// session-map (3.1.4.0 R2; 3.6.0.0 R4 the lit map; 3.6.0.0 R5: every session runs on a map, the old tree went): the
// session running here drawn as its map, compact and read-only (routes/crew/map/LitMini.tsx) -- its boxes, what each
// does now, the helpers it made up -- with a link to Agents -> 3 · Map, where the same map is lit full size. With several
// running, the one on a map first; a session on another machine is listed in the Map's picker, opened on that machine.
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { useScopedCounts } from "../fleet/scope";
import { useFleet } from "../fleet/store";
import { LitMini } from "../crew/map/LitMini";
import { useRunning } from "../crew/map/litStore";

export function MapDetail() {
  const loaded = useFleet((s) => s.loaded);
  const error = useFleet((s) => s.error);
  const any = useFleet((s) => s.harnesses.length);
  const running = useRunning();
  const s = running.find((x) => !!x.map) || running[0];
  if (!loaded) return null; // the section's own wait says it while it reads
  if (error && !any) return <Empty title="Studio could not read the sessions" body={error} />;
  if (!s) return <Empty title="No session is running here" body="Start one (Session's prompt, or halo in a terminal): it is drawn here as its map." />;
  return <LitMini key={s.sid} s={s} />;
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
