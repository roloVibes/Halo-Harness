// Pieces every Flow panel uses: the run state badge, the cost-vs-budget bar,
// the "waiting on you" chip, the empty state before a run is open, and
// opening a panel's Expand face from elsewhere (the palette, the rail).
import { useStateMotion } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { focusPanel, layoutStore, patchPanel } from "../../lib/workspace/persist";
import { cost } from "../orchestra/format";
import { enterWorkspace, runMotion, runState, useFlow } from "./store";

export { Metric } from "../orchestra/bits";

export function FlowBadge({ testid }: { testid?: string }) {
  const state = useFlow(runState);
  const waiting = useFlow((s) => !!s.data?.gate);
  const doneAt = useFlow((s) => s.doneAt);
  const motion = useStateMotion(runMotion(state, waiting, doneAt));
  return (
    <span className="og-badge mono fl-badge" data-state={state || "none"} {...motion} data-testid={testid}>
      {(state || "no run").toUpperCase()}
    </span>
  );
}

/** Cost so far against the budget: a bar that turns amber past 80 % and red past 100 %. */
export function CostBar({ spent, budget, bare }: { spent: number; budget: number | null | undefined; bare?: boolean }) {
  const b = Number(budget) || 0;
  const pct = b > 0 ? Math.min(100, (spent / b) * 100) : 0;
  const tone = b > 0 && spent > b ? "bad" : pct >= 80 ? "warn" : "accent";
  return (
    <div className="fl-cost" title={b ? `${cost(spent)} of ${cost(b)} (${pct.toFixed(0)} %)` : `${cost(spent)}, no budget`}>
      {!bare && (
        <div className="fl-cost-head mono">
          <span>{cost(spent)}</span>
          <span className="muted">{b ? `of ${cost(b)}` : "no budget"}</span>
        </div>
      )}
      <div className="md-bar" role="meter" aria-label="Cost against the budget" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        <span className="md-bar-fill" data-tone={tone} style={{ width: `${b ? pct : 0}%` }} />
      </div>
    </div>
  );
}

/** "WAITING ON YOU" while a gate is open (amber pulse), else nothing. */
export function YouChip() {
  const gate = useFlow((s) => s.data?.gate);
  if (!gate) return null;
  return (
    <button className="fl-you mono" data-motion="waiting" onClick={() => openFlowPanel(gate.step === "approve" || gate.artboards?.length ? "flow-renders" : "flow-step")} title={`${gate.step}: ${gate.position || "you"} decides`}>
      WAITING ON YOU · {gate.step}
    </button>
  );
}

/** Open a Flow panel on its full face (bringing the workspace up first when the Start view shows). */
export function openFlowPanel(id: string, face: "glance" | "detail" = "detail"): void {
  const go = () => {
    patchPanel("flow", id, { collapsed: false, face }, false);
    focusPanel("flow", id);
  };
  enterWorkspace();
  if (layoutStore("flow").get().layout) go();
  else window.setTimeout(go, 120);
}

export function NoFlow({ what }: { what: string }) {
  const loading = useFlow((s) => s.loading);
  const error = useFlow((s) => s.error);
  if (loading) return <div className="og-wait mono muted">loading the flow runs...</div>;
  return (
    <Empty
      title={error ? "Studio could not read the flow runs" : "Open a run from the rail, or write a brief in Intake and press Run."}
      body={error || `${what} fills in from the open run.`}
    />
  );
}
