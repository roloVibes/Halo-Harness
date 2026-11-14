// Agents -> 1 · Agents (3.6.0.0 R1, the v3 design's first tab; docs/STUDIO-builder.md): make an agent -- its name, what
// it does, its model, what it may use, how careful -- try it, save it; or describe it to the builder docked below.
// The room rules (R0a): the form is the main thing, the list a left drawer that opens with the tab (its own default),
// the builder a bar docked at the form's foot. The view bar carries Agents' switch (this tab first, then the views
// R4 retires: Cast, Live, Workflows) and the Attention chip. Nothing opens by itself: no dialog, no conversation.
import { useEffect } from "react";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { AttentionChip } from "../agents/AttentionChip";
import { ViewSwitch } from "../agents/ViewSwitch";
import { AgentsBuilder } from "./Builder";
import { CrewForm } from "./Form";
import { CrewList } from "./List";
import { loadCrew, openAgent, useCrew } from "./store";
import { wireTryFeed } from "./tryStore";

function ListGlance() {
  const n = useCrew((s) => s.agents.length);
  return <div className="glance"><div className="glance-hint">{n} agent{n === 1 ? "" : "s"} of yours. Expand for the list.</div></div>;
}

function FormGlance() {
  const name = useCrew((s) => s.form?.name || "");
  return <div className="glance"><div className="glance-hint">{name ? `${name}: expand for its form.` : "Pick or make an agent."}</div></div>;
}

export const CREW_SECTION = "agents-crew";

function urlAgent(): string {
  try {
    const q = new URLSearchParams(location.search);
    return q.get("view") === "crew" ? (q.get("agent") || "").toLowerCase() : "";
  } catch {
    return "";
  }
}

export const crewPanels: PanelSpec[] = [
  { id: "crew-list", testid: "crew-list-panel", title: "Your agents", role: "drawer", side: "left", startOpen: true, contentW: 360,
    about: "Your agents and this project's, then the starters to copy.",
    help: "Click an agent: its form opens.\n+ New agent starts an empty one.\nA starter's click copies it as yours (Save keeps it).\n`not used yet`: no workflow or map names it.",
    face: "detail", glance: ListGlance, detail: CrewList },
  { id: "crew-form", testid: "crew-form-panel", title: "Agent", role: "main",
    about: "The agent open now: what it does, its model, what it may use, how careful, Try it, More, Save.",
    help: "Change any field; nothing is written until Save.\nWrite it for me fills the builder box below.\nTry it runs it once on a throwaway copy.\nDelete asks on the page first.",
    face: "detail", glance: FormGlance, detail: CrewForm },
  { id: "crew-builder", testid: "crew-builder-panel", title: "Builder", role: "dock",
    about: "Describe an agent, or say what to change: the builder answers with a preview you tick, then Apply.",
    help: "Type what you want and press Enter.\nEach change is a line with a tick; a line that lets an agent do more is never ticked for you.\nApply writes; Undo puts it back.",
    face: "detail", glance: AgentsBuilder, detail: AgentsBuilder },
];

export function CrewView() {
  useEffect(() => {
    void loadCrew().then(() => {
      const named = urlAgent(); // `&agent=<name>`: a link (or a driver) opens that agent's form
      if (named) void openAgent(named);
    });
    wireTryFeed();
  }, []);
  const lead = (
    <span className="cw-lead">
      <ViewSwitch view="crew" />
      <AttentionChip />
    </span>
  );
  return (
    <div className="cw" data-testid="crew">
      <Workspace section={CREW_SECTION} specs={crewPanels} lead={lead} />
    </div>
  );
}
