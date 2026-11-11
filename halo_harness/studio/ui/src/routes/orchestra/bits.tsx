// Two pieces many panels use: the big number (Metric) and a goal run's state badge (3.4.0.0 D: the Runs panels that
// also used the empty state and openPanel went with the runs fold).
import type { ReactNode } from "react";
import { useStateMotion } from "../../lib/motion";
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
