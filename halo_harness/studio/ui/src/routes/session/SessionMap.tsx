// session-map (3.1.4.0 R2; 3.3.11.0 R2 the thumbnail of Roles Live's tree; 3.3.16.0 R2 "the Fleet fold": the Fleet Map
// went, so this panel draws Agents -> Live's own tree, routes/roles/LiveMap.tsx with `thumb`): this harness's sessions
// and each one's agents as a tree, fitted to the panel -- who spawned whom, what each runs on and costs, the tool
// running and for how long, the Steer box's target outlined; a click picks the target, a double-click opens the Agent
// strip, "Open in Agents Live" the same tree full size.
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { useScopedCounts } from "../fleet/scope";
import { useFleet } from "../fleet/store";
import { LiveMap } from "../roles/LiveMap";

export function MapDetail() {
  const loaded = useFleet((s) => s.loaded);
  const error = useFleet((s) => s.error);
  const any = useFleet((s) => s.harnesses.length);
  if (!loaded) return null; // the section's own wait says it while it reads
  if (error && !any) return <Empty title="Studio could not read the sessions" body={error} />;
  return <LiveMap thumb />;
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
      <div className="glance-hint">Expand for the tree: every session here and its agents.</div>
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
