// pm-templates (3.2.0.0 R6; 3.6.0.0 R5): what the selected pack lets you start from -- its workflows with Run <name>:
// the Orchestra new-run form, filled in with the workflow and its inputs. A pack's lineups and bios are no longer read
// (lineups and bios are gone; agents, workflows and maps live in ~/.halo/crew/): the panel says how many it carries.
import { Button, Empty } from "../../../lib/ui";
import { runWorkflow } from "../../orchestra/workflowRun";
import { selected, useMgr } from "./store";
import type { PackRow } from "./types";

function Lists({ p }: { p: PackRow }) {
  return (
    <>
      <div className="rail-label mono">WORKFLOWS</div>
      {p.workflows.length ? (
        <ul className="pm-tpl">
          {p.workflows.map((w) => (
            <li key={w.ref} className="pm-tpl-row" data-testid="pm-workflow" data-ref={w.ref}>
              <span className="mono">{w.ref}</span>
              <span className="muted">{w.stages.join(" -> ")}{w.inputs.length ? ` · inputs ${w.inputs.map((i) => i.name).join(", ")}` : ""}</span>
              <Button size="sm" variant="primary" onClick={() => runWorkflow(w)} title="The Orchestra new-run form, filled in with this workflow" data-testid="pm-run-workflow">Run {w.name}</Button>
            </li>
          ))}
        </ul>
      ) : <p className="muted">No workflow.</p>}
      {(p.lineups.length > 0 || p.bios.length > 0) && (
        <p className="muted" data-testid="pm-templates-old">
          {p.lineups.length} lineup(s) and {p.bios.length} bio(s) in this pack are no longer read: lineups and bios are gone (agents, workflows and maps live in ~/.halo/crew/).
        </p>
      )}
    </>
  );
}

export function TemplatesDetail() {
  const p = useMgr((s) => selected(s));
  if (!p) return <Empty title="Pick a pack" body="Its workflows show here, each with Run." />;
  if (!p.running)
    return (
      <Empty title={p.installed ? "Enable it first" : "Install and enable it first"} testid="pm-templates-off"
             body={`${p.name} offers ${p.lineups.length} lineup(s), ${p.bios.length} bio(s) and ${p.workflows.length} workflow(s); they are read in place while it runs.`} />
    );
  return (
    <div className="pm-templates" data-testid="pm-templates-body" data-id={p.id}>
      <Lists p={p} />
    </div>
  );
}

export function TemplatesGlance() {
  const p = useMgr((s) => selected(s));
  return (
    <div className="glance">
      <div className="glance-kicker mono">TEMPLATES</div>
      <div className="glance-text">{p ? `${p.workflows.length} workflow(s)` : "no pack picked"}</div>
      <div className="glance-hint">Run a workflow</div>
    </div>
  );
}
