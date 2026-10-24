// The bio form (3.0.7.0 R2; bio-form.js in the classic page): the bio open in
// the Bios panel as fields. 3.1.1.0 R3: Studio is the one editor of bios (the
// terminal shows them read-only and opens this form with `e`, `halo agents
// edit` or `halo studio --edit bio:<name>`), so every field the terminal shows
// is here: the identity (description, kind, tags, extends), the sections
// (BioFields.tsx), the schedule and triggers (BioSchedule.tsx), and the whole
// bio as YAML (BioYaml.tsx, for hooks and any key without a field). Each field
// carries field_help.py's line. Save writes it to your scope, or with "Save to
// project scope" to the repo's .halo/agents/ (a shipped bio becomes your
// copy); a 422 lists the validator's lines. 3.0.9.0 R3: a coach card's Apply
// puts its note on top and marks the field it filled in. 3.1.4.0 R4: MODELS
// comes first, right under the name (BioModels: the model select on top).
// 3.2.0.0 R2: a pack's bio opens read-only ("from pack <id>, read-only", the
// fields disabled, Customize instead of Save); a bio asking by
// models.capabilities says what its tags resolve to.
import { useState } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button } from "../../lib/ui";
import { editBio, saveBio, setKey } from "./bioActions";
import { arr, BioFields, BioModels } from "./BioFields";
import { BioSchedule } from "./BioSchedule";
import { BioYaml } from "./BioYaml";
import { CoachNote } from "./CoachNote";
import { Check, ListIn, Pick, TextIn } from "./controls";
import { cloneFromPack } from "./packActions";
import { openDialog, packOf, readOnlySource, roles, scopeLabel, useRoles } from "./store";
import type { Raw } from "./types";

const KINDS = ["main", "subagent", "researcher", "judge", "reviewer", "custom", "media", "planner", "coder", "writer", "ops"];

/** "Save to project scope": where Save (bios and lineups) writes, the repo's .halo/ or your ~/.halo. */
export function ScopeCheck({ what }: { what: string }) {
  const project = useRoles((s) => s.scope === "project");
  return (
    <Check label={`Save to project scope (.halo/${what}/)`} value={project} testid="roles-scope-project"
           onChange={(v) => roles.update(() => ({ scope: v ? "project" : "user" }))} />
  );
}

export function BioForm() {
  const name = useRoles((s) => s.bio);
  const data = useRoles((s) => s.bioData);
  const d = useRoles((s) => s.bioDraft);
  const problems = useRoles((s) => s.bioProblems);
  const busy = useRoles((s) => s.busy === "bio");
  const hint = useRoles((s) => (s.coachHint && s.coachHint.bio === s.bio ? s.coachHint : null));
  const id = useHelpGroup("identity");
  const focusModels = useRoles((s) => s.modelFocus === "bio" && s.bioData?.name === s.bio);
  const [yaml, setYaml] = useState(false);
  const mark = (field: string) => hint?.field === field;
  if (!name) return <p className="muted">Pick a bio above, or drag one onto the canvas to add it to the lineup.</p>;
  if (!d || !data) return problems.length ? <p className="og-problems">{problems[0]}</p> : <div className="og-wait mono muted">reading {name}...</div>;
  const top = (key: string) => (v: unknown) => editBio((r) => setKey(r, key, v));
  const pack = data.pack || packOf(data.scope); // 3.2.0.0 R2: a pack's bio is read-only; Customize makes your copy
  const info = data.model_info;
  return (
    <div className="rb-form" data-testid="bio-form" data-bio={name} data-readonly={pack ? "" : undefined}>
      <header className="re-assign-head">
        <b>{name}</b>
        <span className="rc-scope mono" data-scope={data.scope} data-testid={pack ? "bio-readonly" : undefined}>
          {pack ? `from pack ${pack}, read-only` : readOnlySource(data.scope) ? `${scopeLabel(data.scope)}: saving makes your copy` : scopeLabel(data.scope)}
        </span>
        <button className="re-yaml-toggle mono" aria-pressed={yaml} onClick={() => setYaml(!yaml)} data-testid="bio-yaml-toggle"
                title="Edit the whole bio as YAML (hooks and any key without a field)">YAML</button>
      </header>
      {info && (
        <p className={`mono rb-model-info${info.problem ? " og-problems" : " muted"}`} data-testid="bio-model-info">
          {info.problem ? `models.capabilities ${info.capabilities.join(", ")}: ${info.problem}` : `runs on ${info.ref}: the best catalog model with ${info.capabilities.join(", ")}`}
        </p>
      )}
      {hint && <CoachNote field={hint.field} value={hint.value} run={hint.run} />}
      <fieldset className="rb-fields" disabled={!!pack}>
      {yaml ? (
        <BioYaml />
      ) : (
        <>
          <BioModels d={d} mark={mark} focus={focusModels}
                     inherited={d.models && (d.models as Raw).preference ? "" : String(((data.resolved?.models || {}) as Raw).preference || "")} />
          <TextIn label="Description" hint={id.description} value={String(d.description ?? "")} onCommit={top("description")} testid="bio-description" />
          <Pick label="Kind" hint={id.kind} value={String(d.kind ?? "subagent")} options={KINDS} onChange={top("kind")} testid="bio-kind" />
          <ListIn label="Tags" hint={id.tags} value={arr(d.tags)} onCommit={top("tags")} testid="bio-tags" />
          <TextIn label="Extends" hint={id.extends} placeholder="inherit every section from another bio" value={String(d.extends ?? "")} onCommit={top("extends")} />
          <BioFields d={d} mark={mark} />
          <BioSchedule d={d} />
        </>
      )}
      </fieldset>
      {problems.length > 0 && (
        <div className="re-save-problems" data-testid="bio-problems" role="alert">
          <b>Not saved: the validator says</b>
          <ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      <div className="re-actions rb-actions">
        {pack ? (
          <Button variant="primary" size="sm" disabled={busy} onClick={() => void cloneFromPack("bio", name, true)} title="Clone it into your bios and open your copy" data-testid="bio-customize">Customize</Button>
        ) : (
          <Button variant="primary" size="sm" disabled={busy} onClick={() => void saveBio()} data-testid="bio-save">Save bio</Button>
        )}
        <Button size="sm" variant="ghost" disabled={readOnlySource(data.scope)} onClick={() => openDialog({ kind: "delete-bio", name })} title={readOnlySource(data.scope) ? `A ${scopeLabel(data.scope)} bio cannot be deleted` : "Delete this bio (asks first)"}>Delete</Button>
        <ScopeCheck what="agents" />
      </div>
    </div>
  );
}
