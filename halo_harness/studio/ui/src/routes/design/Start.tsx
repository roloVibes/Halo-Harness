// The Design section before there is a project (3.0.7.0 R3): one Start view
// instead of empty panels -- what Design mode is, how a turn works, and one
// button: name the first project and Create it. DesignView switches to the
// panels as soon as a project exists (one made elsewhere shows within 4 s).
import { useEffect, useState } from "react";
import { Button, Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { SECTION_HELP } from "../sectionHelp";
import { newProject } from "./actions";
import { showsStart, useDesign } from "./store";
import { loadProjects, openProject, startDesign } from "./sync";
import { studio } from "../../lib/store";

export function StartView() {
  const copy = SECTION_HELP.design;
  useEffect(() => {
    // a project made elsewhere (halo design new, a flow) shows up without a reload
    const id = window.setInterval(() => {
      if (document.hidden || studio.get().section !== "design") return;
      void loadProjects().then((rows) => rows[0] && openProject(rows[0].slug));
    }, 4000);
    return () => window.clearInterval(id);
  }, []);
  const [name, setName] = useState("");
  const busy = useDesign((s) => s.busy === "new");
  const error = useDesign((s) => s.error);
  const go = () => void newProject(name);
  return (
    <div className="fl-start ds-start" data-testid="design-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">DESIGN · ON YOUR OWN APPS</div>
          <h1 className="fl-start-title">Design, on your own apps</h1>
          <p className="muted">{copy.what}</p>
        </header>
        <div className="fl-start-grid">
          <Surface className="fl-start-form" motion="idle">
            <label className="fd-field">
              <span className="rail-label mono">NAME YOUR FIRST PROJECT</span>
              <input className="input" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()}
                     placeholder="Launch page" data-testid="design-start-name" />
            </label>
            <div className="ds-go">
              <Button variant="primary" disabled={!name.trim() || busy} onClick={go} data-testid="design-start-create">Create project</Button>
            </div>
            {error && <p className="og-problems">Studio could not read the projects: {error}</p>}
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
          </aside>
        </div>
      </div>
    </div>
  );
}

/** The Design section: the Start view while there is no project, then the panels. */
export function DesignView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startDesign(), []);
  const loaded = useDesign((s) => s.projects !== null);
  const start = useDesign(showsStart);
  if (!loaded)
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">reading the design projects...</div>
      </div>
    );
  if (start) return <StartView />;
  return <Workspace section={section} specs={specs} />;
}
