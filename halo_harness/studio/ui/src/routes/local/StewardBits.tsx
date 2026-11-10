// The steward's block (3.3.4.0 R5 as the Fleet Ollama panel's; 3.3.16.0 R2: Local -> Steward's pieces): the job's status line (where it runs, since when, its model,
// the last run), its last note (the cost line muted), the findings for the picked host (severity, the line, the
// evidence numbers; in `review` mode Apply and Dismiss; Dismiss keeps one quiet for 24 hours), and in `auto`
// mode the changes it made, Undo on the newest. Server-side hints are never applied: the plan block copies them.
import { Button, Icon } from "../../lib/ui";
import { applyFinding, dismissFinding, runNow, undoLast, useOllama, type Change, type Finding, type Note } from "./ostore";

const COST = /^\(steward model /;
const NO_CHANGES: Change[] = []; // one empty list: a selector that answered a new [] each read would render forever

export function NoteLines({ note, testid = "ollama-note" }: { note: Note | null; testid?: string }) {
  if (!note) return <p className="muted oll-note" data-testid={testid}>No note yet: the steward writes one when its rules find something new.</p>;
  const lines = note.lines?.length ? note.lines : [note.say];
  return (
    <div className="oll-note" data-testid={testid}>
      {lines.map((l, i) => (
        <p key={i} className={COST.test(l) ? "muted mono oll-cost" : i === 0 ? "oll-note-first" : ""}>{l}</p>
      ))}
      {note.cost && !lines.some((l) => COST.test(l)) && <p className="muted mono oll-cost">{note.cost}</p>}
    </div>
  );
}

function Numbers({ f }: { f: Finding }) {
  const nums = Object.entries(f.evidence?.numbers || {}).filter(([, v]) => v !== null && v !== undefined && typeof v !== "object");
  if (!nums.length) return null;
  return <div className="oll-evidence mono muted">{nums.map(([key, v]) => `${key} ${v}`).join(" · ")}</div>;
}

export function FindingRow({ f, review }: { f: Finding; review: boolean }) {
  const busy = useOllama((s) => s.busy);
  const p = f.proposal;
  return (
    <li className="oll-finding" data-testid="ollama-finding" data-id={f.id} data-rule={f.rule} data-severity={f.severity} data-applied={f.applied ? "yes" : undefined}>
      <div className="oll-finding-top">
        <span className="og-chip mono" data-severity={f.severity}>{f.severity}</span>
        <span className="mono muted">{f.model}</span>
        {f.runtime && (
          <span className="og-chip mono" data-testid="ollama-finding-runtime" title={`a local server: ${f.server || f.host}`}>{f.runtime}</span>
        )}
        <span className="spacer" />
        {f.applied && <span className="og-chip mono" data-testid="ollama-applied" data-tone="ok">applied</span>}
        {!f.applied && f.proposed && <span className="og-chip mono">proposed</span>}
      </div>
      <div className="oll-finding-line">{f.finding}</div>
      {p && (
        <div className="oll-change mono">
          {p.field} {String(p.from ?? "unset")} → {String(p.to)} <span className="muted">({p.why})</span>
        </div>
      )}
      <Numbers f={f} />
      <div className="oll-actions">
        {review && p && !f.applied && (
          <Button size="sm" variant="primary" disabled={!!busy} onClick={() => void applyFinding(f.id)} data-testid="ollama-apply">Apply</Button>
        )}
        {!f.applied && (
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => void dismissFinding(f.id)} data-testid="ollama-dismiss" title="keep this finding quiet for 24 hours">Dismiss</Button>
        )}
      </div>
    </li>
  );
}

function Changes() {
  const changes = useOllama((s) => s.steward?.changes || NO_CHANGES);
  const busy = useOllama((s) => s.busy);
  if (!changes.length) return <p className="muted">No change of the steward's is in place.</p>;
  return (
    <ul className="oll-changes">
      {changes.map((c, i) => (
        <li key={c.id} className="oll-change-row mono" data-testid="ollama-change" data-id={c.id}>
          <span>{c.say || `${c.field} ${String(c.from ?? "unset")} → ${String(c.to)} for ${c.key}`}</span>
          <span className="spacer" />
          {i === changes.length - 1 && <Button size="sm" variant="ghost" icon={<Icon name="reset" />} disabled={!!busy} onClick={() => void undoLast()} data-testid="ollama-undo">Undo</Button>}
        </li>
      ))}
    </ul>
  );
}

/** 3.3.16.0 R2 (from the Fleet Ollama panel's steward block; the status lines, the note and the findings are Local ->
 *  Steward's own): Run now, the hub's note when this box is a member, and in `auto` mode the changes in place with Undo. */
export function StewardRunAndChanges() {
  const st = useOllama((s) => s.steward);
  const busy = useOllama((s) => s.busy);
  const mode = useOllama((s) => s.steward?.mode || s.hosts?.mode || "");
  return (
    <div className="oll-block" data-testid="local-steward-run">
      <div className="oll-head">
        <span className="rail-label mono">MODE · {mode.toUpperCase() || "?"}</span>
        <span className="spacer" />
        <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => void runNow()} data-testid="ollama-run" title="one pass of the rules now (no model call)">Run now</Button>
      </div>
      {st?.hub_note?.line && <p className="muted oll-hub" data-testid="ollama-hub-note">steward on {st.hub_note.hub || "the hub"}: {st.hub_note.line}</p>}
      {mode === "auto" && (
        <>
          <div className="rail-label mono">CHANGES IN PLACE</div>
          <Changes />
        </>
      )}
    </div>
  );
}
