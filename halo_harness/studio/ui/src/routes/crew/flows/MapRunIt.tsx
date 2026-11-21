// Run it on a workflow box's card on the Map (3.6.0.6 P), on a map of the owner's own and on a scratch map alike: the
// box's workflow, with the scope and problems of its row in GET crew/workflows (one that ships with Halo: none, Copy
// makes it yours). A press inside it never reaches the box (no toggle, no drag).
import { useEffect } from "react";
import { flows, loadFlows, useFlows } from "./flowStore";
import { RunFlow } from "./RunFlow";

const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

export function MapRunIt({ name, box }: { name: string; box: string }) {
  const row = useFlows((s) => s.flows.find((f) => f.name === name));
  useEffect(() => { if (!flows.get().loaded) void loadFlows(); }, []);
  if (!row) return null;
  return (
    <div className="rf-map" onClick={stop} onPointerDown={stop} onKeyDown={stop} data-testid="map-run-flow" data-box={box}>
      <RunFlow name={row.name} scope={row.scope} problems={row.problems} where={`map:${box}`} />
    </div>
  );
}
