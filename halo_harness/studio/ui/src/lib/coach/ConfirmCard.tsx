// A coach card's confirm card (3.1.3.0 R1): what Apply is about to write --
// the file (new, or changed), the before -> after diff in mono (added lines
// cyan, removed amber) -- with Apply and Cancel. Nothing is written until
// Apply here; Undo on the card puts the file back afterwards. 3.1.6.0 R2: a
// probe card's confirm lists every file and one diff per file, one after another.
import { Button } from "../ui";
import { cancelApply, confirmApply } from "./actions";
import type { CoachPreview, CoachRunKind } from "./types";

function lineKind(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "file";
  if (line.startsWith("@@")) return "hunk";
  if (line.startsWith("+")) return "add";
  if (line.startsWith("-")) return "del";
  return "ctx";
}

export function ConfirmCard({ kind, run, p, busy }: { kind: CoachRunKind; run: string; p: CoachPreview; busy: string }) {
  const value = Array.isArray(p.value) ? p.value.join(", ") : String(p.value);
  return (
    <div className="cc-confirm" data-testid="coach-confirm" data-file={p.file} role="group" aria-label="Confirm Apply">
      <div className="cc-confirm-head mono">
        <span className="glance-kicker">APPLY · {p.target.toUpperCase()}</span>
        <span className="cc-confirm-what">{p.name ? `${p.name}: ` : ""}{p.field} = {value}</span>
      </div>
      <div className="cc-confirm-file mono" data-testid="coach-confirm-file" title={p.files ? "The files Apply writes" : "The file Apply writes"}>
        {p.files ? p.files.join("\n") : p.file}{p.exists ? "" : p.files ? "  (a new file among them: Apply creates it)" : "  (new: Apply creates it)"}
      </div>
      {(p.skipped || []).map((s, i) => <div key={i} className="cc-hint muted mono">Apply leaves out {s}</div>)}
      <pre className="cc-diff mono" data-testid="coach-diff" aria-label="Before and after">
        {(p.diff.length ? p.diff : ["(no change: the file already holds it)"]).map((line, i) => (
          <span key={i} className="cc-diff-line" data-line={lineKind(line)}>{line + "\n"}</span>
        ))}
      </pre>
      <div className="cc-actions">
        <span className="muted cc-hint">Writes this file now; Undo on the card puts it back.</span>
        <span className="spacer" />
        <Button size="sm" variant="ghost" onClick={() => cancelApply(kind, run, p.id)} data-testid="coach-confirm-cancel"
                title="Close the confirm card; nothing is written">Cancel</Button>
        <Button size="sm" variant="primary" disabled={busy === "apply"} onClick={() => void confirmApply(kind, run, p.id)}
                data-testid="coach-confirm-apply" title="Write the change shown above">
          {busy === "apply" ? "Writing..." : "Apply"}
        </Button>
      </div>
    </div>
  );
}
