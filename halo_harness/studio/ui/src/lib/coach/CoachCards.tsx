// The coach's cards (3.0.9.0 R3), shared by the Orchestra, mission and
// team report faces: the suggestions grouped by kind, each with its severity
// chip, the lane or part it is about, the text, the evidence ("why") in mono,
// and Dismiss (hidden for this run in this browser; "Show dismissed" brings
// them back). 3.1.3.0 R1 closes the loop on each card: "Ask the model" (the
// run's lead explains the card in one paragraph, kept with the run), Apply
// (the confirm card -- the file and the diff -- then the write; ConfirmCard),
// the Applied / Undone chip with Undo, and Edit (the face's editor opened
// with the change filled in, nothing saved: the 3.0.9.0 Apply). 3.1.6.0 R2:
// an Orchestra run's header row has Probe (ProbeBar.tsx); the probe's card
// leads the list with its contrast table, the judge's why in the paragraph
// slot, and Apply = the composed overlay (several files, one Undo). 3.1.6.0
// R3: the library's line and its "Library (n)" fold (LibraryFold.tsx) under
// the header row, and a `lib` chip on a card an earlier entry also made.
import { useEffect, useState } from "react";
import { Button, Empty } from "../ui";
import { askModel, cardKey, previewApply, undoApply } from "./actions";
import { ConfirmCard } from "./ConfirmCard";
import { LibraryFold } from "./LibraryFold";
import { ContrastTable, ProbeButton, ProbePanel } from "./ProbeBar";
import { dismiss, keyOf, loadCoach, restoreAll, useCoach } from "./store";
import { KIND_LABEL, KIND_ORDER, type CoachRunKind, type Suggestion } from "./types";

const NONE: string[] = [];

export type ApplyFn = (s: Suggestion, run: string) => void;

function editTitle(s: Suggestion): string {
  const a = s.apply;
  if (!a) return "";
  const value = Array.isArray(a.value) ? a.value.join(", ") : String(a.value);
  if (a.target === "bio") return `Opens bio ${a.name} in Roles with ${a.field} = ${value} filled in; Save there keeps it`;
  if (a.target === "lineup") return `Opens the Lineup tab in Roles: ${a.field} = ${value}`;
  return `Opens the plan editor on this run with ${a.field} = ${value} staged`;
}

function Lead({ s, busy, onAsk }: { s: Suggestion; busy: string; onAsk: (refresh: boolean) => void }) {
  if (busy === "ask") return <div className="cc-lead mono muted" data-testid="coach-asking">asking the run's lead...</div>;
  const probe = s.kind === "probe";
  if (s.paragraph)
    return (
      <div className="cc-lead" data-testid="coach-paragraph">
        <span className="glance-kicker mono">{probe ? "THE JUDGE" : "THE LEAD"}</span>
        <p>{s.paragraph}</p>
        {!probe && (
          <Button size="sm" variant="ghost" onClick={() => onAsk(true)} title="Ask the lead again (a new model call)"
                  data-testid="coach-ask-again">Ask again</Button>
        )}
      </div>
    );
  return s.paragraph_error ? <div className="cc-lead-error mono" data-testid="coach-paragraph-error">the lead could not answer: {s.paragraph_error}</div> : null;
}

function Card({ s, run, kind, onEdit }: { s: Suggestion; run: string; kind: CoachRunKind; onEdit?: ApplyFn }) {
  const busy = useCoach((st) => st.busy[cardKey(kind, run, s.id)] || "");
  const confirm = useCoach((st) => st.confirm[cardKey(kind, run, s.id)]);
  const where = s.lane_or_part === null || s.lane_or_part === "" ? "" : kind === "mission" ? `part ${s.lane_or_part}`
    : kind === "orchestra" ? `lane ${s.lane_or_part}` : `${kind === "team" ? "stage" : "step"} ${s.lane_or_part}`;
  const applied = s.applied?.state === "applied";
  return (
    <article className="cc-card" data-testid="coach-card" data-id={s.id} data-kind={s.kind} data-severity={s.severity}
             data-applied={s.applied?.state || ""}>
      <header className="cc-card-head">
        <span className="og-chip mono cc-sev" data-severity={s.severity}>{s.severity}</span>
        {!!s.library_hits?.length && (
          <span className="og-chip mono cc-lib-chip" data-testid="coach-lib" data-entries={s.library_hits.join(" ")}
                title={`The library: ${s.library_hits.join(", ")} made this same change in earlier runs like this one`}>lib</span>
        )}
        {where && <span className="mono muted cc-where">{where}</span>}
        {s.bio && <span className="og-chip mono cc-bio" title="the bio this lane ran as">{s.bio}</span>}
        <span className="spacer" />
        {s.applied && (
          <span className="og-chip mono cc-state" data-state={s.applied.state} data-testid="coach-applied"
                title={`${s.applied.apply_id}: ${s.applied.file}`}>{applied ? "APPLIED" : "UNDONE"}</span>
        )}
      </header>
      <p className="cc-text">{s.text}</p>
      {s.table && s.table.length > 0 && <ContrastTable rows={s.table} />}
      <ul className="cc-why mono" data-testid="coach-why" aria-label="Why">
        {s.why.map((w, i) => <li key={i}>{w}</li>)}
      </ul>
      <Lead s={s} busy={busy} onAsk={(refresh) => void askModel(kind, run, s.id, refresh)} />
      {confirm && <ConfirmCard kind={kind} run={run} p={confirm} busy={busy} />}
      <div className="cc-actions">
        {!s.paragraph && busy !== "ask" && s.kind !== "probe" && (
          <Button size="sm" variant="ghost" onClick={() => void askModel(kind, run, s.id)} data-testid="coach-ask"
                  title="The run's lead explains this card in one paragraph (one model call; kept with the run)">Ask the model</Button>
        )}
        {s.apply && !applied && !confirm && (
          <Button size="sm" variant="primary" disabled={busy === "preview"} onClick={() => void previewApply(kind, run, s.id)}
                  title="Shows the file and the change first; nothing is written until you confirm" data-testid="coach-apply">Apply</Button>
        )}
        {applied && s.applied && (
          <Button size="sm" variant="default" disabled={busy === "undo"} onClick={() => void undoApply(kind, run, s.id, s.applied!.apply_id)}
                  title="Puts the file back as it was before Apply (if nothing changed it since)" data-testid="coach-undo">Undo</Button>
        )}
        {s.apply && onEdit && s.apply.target !== "overlay" && (
          <Button size="sm" variant="ghost" onClick={() => onEdit(s, run)} title={editTitle(s)} data-testid="coach-edit">Edit</Button>
        )}
        {!s.apply && <span className="muted cc-hint">{s.kind === "probe" ? "nothing to write: the run's harness stays" : "nothing to write: change it by hand"}</span>}
        <span className="spacer" />
        <Button size="sm" variant="ghost" onClick={() => dismiss(kind, run, s.id)} title="Hide this card for this run" data-testid="coach-dismiss">Dismiss</Button>
      </div>
    </article>
  );
}

export function CoachCards({ kind, run, onEdit }: { kind: CoachRunKind; run: string; onEdit?: ApplyFn }) {
  useEffect(() => void loadCoach(kind, run), [kind, run]);
  const entry = useCoach((s) => s.runs[keyOf(kind, run)]);
  const hidden = useCoach((s) => s.dismissed[keyOf(kind, run)] || NONE);
  const [showAll, setShowAll] = useState(false);
  if (!entry || (entry.loading && !entry.result)) return <div className="og-wait mono muted">reading the run's files...</div>;
  if (!entry.result) return <Empty title="Studio could not read the coach" body={entry.error} />;
  const all = entry.result.suggestions;
  const shown = showAll ? all : all.filter((s) => !hidden.includes(s.id));
  const nHidden = all.length - all.filter((s) => !hidden.includes(s.id)).length;
  const nApplied = all.filter((s) => s.applied?.state === "applied").length;
  return (
    <div className="cc" data-testid="coach" data-run={run} data-kind={kind}>
      <div className="cc-head mono muted">
        <span data-testid="coach-summary">{all.length ? `${all.length} suggestion${all.length === 1 ? "" : "s"} from the run's files, ${nApplied} applied` : "nothing to suggest"}</span>
        <span className="spacer" />
        {nHidden > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setShowAll((v) => !v)} data-testid="coach-show-dismissed">
            {showAll ? "Hide dismissed" : `Show dismissed (${nHidden})`}
          </Button>
        )}
        {showAll && nHidden > 0 && <Button size="sm" variant="ghost" onClick={() => restoreAll(kind, run)}>Restore all</Button>}
        {kind === "orchestra" && <ProbeButton run={run} />}
      </div>
      {kind === "orchestra" && <ProbePanel run={run} />}
      <LibraryFold kind={kind} run={run} />
      {all.length > 0 && (
        <p className="cc-help muted" data-testid="coach-help">
          Ask the model: the run's lead explains a card. Apply: shows the file and the diff, writes after you confirm.
          Undo: puts the file back. Edit: opens the editor with the change filled in, nothing saved.
          {kind === "orchestra" && " Probe: runs the goal again under two candidate setups and offers what the deliverables support."}
        </p>
      )}
      {!all.length && <Empty title="Nothing to coach" body="The run's files show no lane sent back twice, no denied tool, no long wait and no gate that looped." testid="coach-empty" />}
      {KIND_ORDER.map((k) => {
        const rows = shown.filter((s) => s.kind === k);
        if (!rows.length) return null;
        return (
          <section key={k} className="cc-group" data-kind={k}>
            <div className="rail-label mono">{KIND_LABEL[k]} · {rows.length}</div>
            {rows.map((s) => <Card key={s.id} s={s} run={run} kind={kind} onEdit={onEdit} />)}
          </section>
        );
      })}
    </div>
  );
}
