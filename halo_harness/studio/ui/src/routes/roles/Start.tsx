// The Roles section before you have a lineup of your own (3.0.7.0 R2): one
// Start view instead of six empty panels -- what a lineup is, the steps
// (lineup -> bios -> tiers -> apply), and one button: Make my first lineup
// (a copy of a shipped one, opened in the editor). It shows while only the
// shipped lineups exist and none of them is active; "open the panels anyway"
// (or ?view=workspace) goes straight to the panels.
import { useEffect } from "react";
import { Button, Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { SECTION_HELP } from "../sectionHelp";
import { openDialog, setView, showsStart, useRoles } from "./store";
import { startRoles } from "./sync";
import { useRolesKeys } from "./keys";
import { NextStep } from "../NextStep";

export function StartView() {
  const copy = SECTION_HELP.roles;
  const shippedNames = useRoles((s) => s.lineups.map((l) => l.name).join(",")).split(",").filter(Boolean);
  const from = shippedNames.includes("balanced") ? "balanced" : shippedNames[0] || "";
  return (
    <div className="fl-start rs-start" data-testid="roles-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">ROLES · WHO DOES WHAT</div>
          <h1 className="fl-start-title">Your team of agents</h1>
          <p className="muted">{copy.what}</p>
        </header>
        <div className="fl-start-grid">
          <Surface className="fl-start-form" motion="idle">
            <div className="os-where">
              <p>
                You have only the lineups Halo ships ({shippedNames.length}). Make your own copy of one: you can then edit every card, its model and its tier, and Apply it.
              </p>
              <div className="os-buttons">
                <Button variant="primary" onClick={() => openDialog({ kind: "new-lineup", from })} data-testid="roles-start-new">Make my first lineup</Button>
              </div>
            </div>
          </Surface>
          <aside className="fl-start-side">
            <ol className="fl-explain">
              {copy.steps.map(([title, text], i) => (
                <li key={title}>
                  <span className="fl-explain-n mono">{i + 1}</span>
                  <span>
                    <b>{title}</b>
                    <span className="fl-explain-text">{text}</span>
                  </span>
                </li>
              ))}
            </ol>
            <button className="og-link mono" onClick={() => setView("workspace")} data-testid="roles-open-workspace">open the panels anyway</button>
          </aside>
        </div>
        <NextStep from="roles" />
      </div>
    </div>
  );
}

/** The Roles section: the Start view while you have no lineup of your own, then the panels. */
export function RolesView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startRoles(), []);
  useRolesKeys();
  const loaded = useRoles((s) => s.loaded);
  const start = useRoles(showsStart);
  if (!loaded)
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">reading the lineups...</div>
      </div>
    );
  if (start) return <StartView />;
  return <Workspace section={section} specs={specs} />;
}
