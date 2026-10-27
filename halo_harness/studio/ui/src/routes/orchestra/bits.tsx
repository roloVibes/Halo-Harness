// Pieces every Orchestra panel uses: the big number, the run state badge,
// and the empty state shown before a run is open.
import type { ReactNode } from "react";
import { Empty } from "../../lib/ui";
import { useStateMotion } from "../../lib/motion";
import { focusPanel, patchPanel } from "../../lib/workspace/persist";
import { runMotion, useOrch } from "./store";
import type { RunState } from "./types";

export function Metric({ value, label, tone }: { value: ReactNode; label: string; tone?: "ok" | "warn" | "bad" | "accent" }) {
  return (
    <div className="metric" data-tone={tone}>
      <span className="metric-value mono">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

export function StateBadge({ state }: { state: RunState | undefined }) {
  const doneAt = useOrch((s) => s.doneAt);
  const motion = useStateMotion(runMotion(state, doneAt));
  return (
    <span className="og-badge mono" data-state={state || "none"} {...motion} data-testid="run-state">
      {(state || "no run").toUpperCase()}
    </span>
  );
}

/** Open a panel's Expand face and focus it (palette commands, "new run"). */
export function openPanel(id: string): void {
  patchPanel("orchestra", id, { collapsed: false, face: "detail" }, false);
  focusPanel("orchestra", id);
}

export function NoRun({ what }: { what: string }) {
  const loading = useOrch((s) => s.loading);
  const error = useOrch((s) => s.error);
  if (loading) return <div className="og-wait mono muted">loading the runs...</div>;
  return (
    <Empty
      title={error ? "Studio could not read the runs" : "No run yet"}
      body={error || `${what} appears once a run starts. Press + in the header, then New run, write the goal and press Run (or halo orchestra run in a terminal).`}
    />
  );
}
