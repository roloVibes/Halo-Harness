// The lineup's header fields and the save problems (3.0.7.0 R2, out of LineupTab.tsx in 3.3.16.0 R1b): Description,
// How the pieces work together (TextBoxes, 3.3.15.0 R3), Extends and where Save writes; the Description page of the
// inspector draws them. A save that answers 422 lists the validator's lines above the summary or the page.
import { useHelpGroup } from "../../lib/fieldHelp";
import { edit } from "./actions";
import { ScopeCheck } from "./BioForm";
import { TextIn } from "./controls";
import { useRoles } from "./store";

export function LineupHeader() {
  const raw = useRoles((s) => s.raw);
  const h = useHelpGroup("assignment");
  if (!raw) return null;
  const put = (key: string) => (v: string) => edit((r) => (v ? (r[key] = v) : delete r[key]));
  return (
    <div className="re-form">
      <TextIn label="Description" area hint={h.description} value={String(raw.description ?? "")} onCommit={put("description")} testid="roles-description" />
      <TextIn label="How the pieces work together" area hint={h.about} value={String(raw.about ?? "")} onCommit={put("about")} testid="roles-about" />
      <TextIn label="Extends" hint={h.extends} placeholder="another lineup to inherit sections from" value={String(raw.extends ?? "")} onCommit={put("extends")} />
      <ScopeCheck what="teams" />
    </div>
  );
}

export function SaveProblems() {
  const lines = useRoles((s) => s.saveProblems);
  if (!lines.length) return null;
  return (
    <div className="re-save-problems" data-testid="roles-save-problems" role="alert">
      <b>Not saved: the validator says</b>
      <ul>{lines.map((l) => <li key={l}>{l}</li>)}</ul>
    </div>
  );
}
