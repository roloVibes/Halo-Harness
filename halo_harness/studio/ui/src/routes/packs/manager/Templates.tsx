// pm-templates (3.2.0.0 R6): what the selected pack lets you start from -- its
// lineups and bios with R2's Roles actions, reused (Preview opens it read-only
// in Roles, Clone copies it into your files, Customize clones it and opens
// your copy, Apply makes a lineup the one new sessions use, asking first), and
// its workflows with Run <name>: the Orchestra new-run form, filled in with
// the workflow and its inputs. A pack's bios and lineups are read in place
// while it runs, so a disabled pack offers none yet.
import { Button, Empty } from "../../../lib/ui";
import { goSection } from "../../../lib/store";
import { applyEdit } from "../../../shell/edit";
import { applyFromPack, cloneFromPack } from "../../roles/packActions";
import { setView as rolesView } from "../../roles/store";
import { startRoles } from "../../roles/sync";
import { runWorkflow } from "../../orchestra/workflowRun";
import { selected, useMgr } from "./store";
import type { PackRow } from "./types";

type Kind = "bio" | "lineup";

function toRoles(): void {
  goSection("roles");
  rolesView("workspace");
  startRoles();
}

const preview = (kind: Kind, name: string) => void applyEdit({ kind, name, text: `${kind}:${name}` });

async function customize(kind: Kind, name: string): Promise<void> {
  toRoles();
  await cloneFromPack(kind, name, true);
}

async function apply(name: string): Promise<void> {
  toRoles();
  await applyFromPack(name);
}

function Acts({ kind, name }: { kind: Kind; name: string }) {
  return (
    <span className="rlu-acts" data-testid="pm-template-actions">
      <Button size="sm" variant="ghost" onClick={() => preview(kind, name)} title="Open it in Roles, read-only" data-testid="pm-preview">Preview</Button>
      <Button size="sm" variant="ghost" onClick={() => void cloneFromPack(kind, name, false)} title={`Copy it into your ${kind}s (asks first if one has the name)`} data-testid="pm-clone">Clone</Button>
      <Button size="sm" variant="ghost" onClick={() => void customize(kind, name)} title="Clone it and open your copy in Roles" data-testid="pm-customize">Customize</Button>
      {kind === "lineup" && <Button size="sm" onClick={() => void apply(name)} title="Make it the lineup new sessions use (asks first)" data-testid="pm-apply">Apply</Button>}
    </span>
  );
}

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
      <div className="rail-label mono">LINEUPS</div>
      {p.lineups.length ? (
        <ul className="pm-tpl">
          {p.lineups.map((l) => (
            <li key={l.name} className="pm-tpl-row" data-testid="pm-template" data-kind="lineup" data-name={l.name}>
              <span className="mono">{l.name}</span>
              <span className="muted">{l.members.map((m) => `${m.agent} (${m.role})`).join(", ")}{l.tiers ? ` · ${l.tiers} tiers` : ""}</span>
              <Acts kind="lineup" name={l.name} />
            </li>
          ))}
        </ul>
      ) : <p className="muted">No lineup.</p>}
      <div className="rail-label mono">BIOS</div>
      {p.bios.length ? (
        <ul className="pm-tpl">
          {p.bios.map((b) => (
            <li key={b.name} className="pm-tpl-row" data-testid="pm-template" data-kind="bio" data-name={b.name}>
              <span className="mono">{b.name}</span>
              <span className="muted">{b.kind || "?"} · runs on {b.line}</span>
              <Acts kind="bio" name={b.name} />
            </li>
          ))}
        </ul>
      ) : <p className="muted">No bio.</p>}
    </>
  );
}

export function TemplatesDetail() {
  const p = useMgr((s) => selected(s));
  if (!p) return <Empty title="Pick a pack" body="Its lineups, bios and workflows show here, each with what you can do with it." />;
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
      <div className="glance-text">{p ? `${p.lineups.length} lineup(s), ${p.bios.length} bio(s), ${p.workflows.length} workflow(s)` : "no pack picked"}</div>
      <div className="glance-hint">Preview, Clone, Customize, Apply, Run</div>
    </div>
  );
}
