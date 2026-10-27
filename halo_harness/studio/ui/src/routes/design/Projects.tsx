// design-projects (3.0.7.0 R3): every design project (its artboards and its
// model); click one to open it in the other panels, New project makes one
// (a dialog: a name and, if you like, the project's model). 3.1.4.0 R4: the
// open project's model on top, the model select to change it (PUT
// design/<slug>/model; its first option keeps the default model).
import { useHelpGroup } from "../../lib/fieldHelp";
import type { MotionState } from "../../lib/motion";
import { Button, Empty } from "../../lib/ui";
import { ModelSelect } from "../shared/ModelSelect";
import { useResolved } from "../shared/resolve";
import { setProjectModel } from "./actions";
import { openDialog, useDesign } from "./store";
import { openProject } from "./sync";

export function ProjectsDetail() {
  const rows = useDesign((s) => s.projects);
  const slug = useDesign((s) => s.slug);
  const error = useDesign((s) => s.error);
  const meta = useDesign((s) => (s.slug && s.data ? s.data.meta : null));
  const busy = useDesign((s) => s.busy === "model");
  const def = useResolved("");
  const help = useHelpGroup("model_select");
  if (rows === null) return null; // 3.3.2.0 R3: the section's own wait says it while it reads (DesignView)
  return (
    <div className="dp">
      <div className="dp-bar">
        <Button size="sm" variant="primary" onClick={() => openDialog({ kind: "new" })} data-testid="design-new">New project</Button>
      </div>
      {meta && (
        <ModelSelect label={`${meta.name}'s model`} hint={help.design} value={meta.model || ""} onPick={(m) => void setProjectModel(m)} busy={busy}
                     inherit={{ label: "the default", model: def?.ref || "" }} testid="design-project-model" compact />
      )}
      {error && <p className="og-problems">{error}</p>}
      {rows.length ? (
        <ul className="dp-list">
          {rows.map((p) => (
            <li key={p.slug}>
              <button className="dp-row" aria-pressed={p.slug === slug} onClick={() => p.slug !== slug && void openProject(p.slug)} data-testid="design-project">
                <b>{p.name}</b>
                <span className="og-chip mono">{p.artboards} artboard{p.artboards === 1 ? "" : "s"}</span>
                <span className="dp-model mono muted">{p.model || "default model"}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <Empty title="No projects yet" body="New project makes the first one." />
      )}
    </div>
  );
}

export function ProjectsGlance() {
  const n = useDesign((s) => s.projects?.length || 0);
  const name = useDesign((s) => s.data?.meta.name || "");
  return (
    <div className="glance">
      <div className="glance-kicker mono">{n} PROJECT{n === 1 ? "" : "S"}</div>
      <div className="glance-text">{name || "none open"}</div>
    </div>
  );
}

export function useProjectsMotion(): MotionState {
  const error = useDesign((s) => !!s.error);
  const n = useDesign((s) => s.projects?.length || 0);
  return error ? "error" : n ? "idle" : "none";
}
