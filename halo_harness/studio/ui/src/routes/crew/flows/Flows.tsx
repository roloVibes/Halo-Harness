// Agents -> 2 · Workflows (3.6.0.0 R2, the v3 design's second tab; docs/STUDIO-workflows.md): make a workflow -- your
// agents in steps, in order -- try it, save it; or describe it to the builder docked below. The room rules (R0a): the
// form (with the steps drawn beside it) is the main thing, the list a left drawer that opens with the tab, the builder a
// bar docked at the form's foot. The view bar carries Agents' switch and the Attention chip. Nothing opens by itself.
import { useEffect } from "react";
import { Workspace } from "../../../lib/workspace/Workspace";
import type { PanelSpec } from "../../../lib/workspace/types";
import { AttentionChip } from "../../agents/AttentionChip";
import { ViewSwitch } from "../../agents/ViewSwitch";
import { FlowsBuilder } from "../Builder";
import { loadCrew, useCrew } from "../store";
import { FlowForm } from "./FlowForm";
import { FlowList } from "./FlowList";
import { loadFlows, openFlow, useFlows } from "./flowStore";
import { showFlowTry, wireFlowTryFeed } from "./flowRun";

export const FLOWS_SECTION = "agents-flows";

function ListGlance() {
  const n = useFlows((s) => s.flows.length);
  return <div className="glance"><div className="glance-hint">{n} workflow{n === 1 ? "" : "s"} of yours. Expand for the list.</div></div>;
}

function FormGlance() {
  const name = useFlows((s) => s.form?.name || "");
  return <div className="glance"><div className="glance-hint">{name ? `${name}: expand for its form.` : "Pick or make a workflow."}</div></div>;
}

function fromUrl(): { name: string; run: string } {
  try {
    const q = new URLSearchParams(location.search);
    return q.get("view") === "flows" ? { name: (q.get("workflow") || "").toLowerCase(), run: q.get("try") || "" } : { name: "", run: "" };
  } catch {
    return { name: "", run: "" };
  }
}

export const flowPanels: PanelSpec[] = [
  { id: "flow-list", testid: "flow-list-panel", title: "Your workflows", role: "drawer", side: "left", startOpen: true, contentW: 360,
    about: "Your workflows and this project's (on the map or not), then the starters to copy.",
    help: "Click a workflow: its form opens.\n+ New workflow starts an empty one.\nA starter's click copies it as yours (Save keeps it).",
    face: "detail", glance: ListGlance, detail: FlowList },
  { id: "flow-form", testid: "flow-form-panel", title: "Workflow", role: "main",
    about: "The workflow open now: what it is for, its steps in order, what it costs, Try it, Save; the steps drawn beside it.",
    help: "Change any field; nothing is written until Save.\nWrite it for me fills the builder box below.\nTry it runs every step once on a throwaway copy.\nDelete asks on the page first.",
    face: "detail", glance: FormGlance, detail: FlowForm },
  { id: "flow-builder", testid: "flow-builder-panel", title: "Builder", role: "dock",
    about: "Describe a workflow, or say what to change: the builder answers with a preview you tick, then Apply.",
    help: "Type what you want and press Enter.\nEach change is a line with a tick; a line that lets an agent do more is never ticked for you.\nApply writes; Undo puts it back.",
    face: "detail", glance: FlowsBuilder, detail: FlowsBuilder },
];

export function FlowsView() {
  const agentsLoaded = useCrew((s) => s.loaded);
  useEffect(() => {
    void loadFlows().then(() => {
      const u = fromUrl(); // `&workflow=<name>` opens it; `&try=<id>` shows a run (a link, a driver, an Attention row)
      if (u.name) void openFlow(u.name).then(() => u.run && void showFlowTry(u.run));
    });
    if (!agentsLoaded) void loadCrew();
    wireFlowTryFeed();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const lead = (
    <span className="cw-lead">
      <ViewSwitch view="flows" />
      <AttentionChip />
    </span>
  );
  return (
    <div className="cw" data-testid="flows">
      <Workspace section={FLOWS_SECTION} specs={flowPanels} lead={lead} />
    </div>
  );
}
