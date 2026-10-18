// The coach's cards (3.0.9.0 R3), shared by the Orchestra, flow, mission and
// team report faces: the suggestions grouped by kind, each with its severity
// chip, the lane or part it is about, the text, the evidence ("why") in mono,
// Apply when the suggestion names a change (the face says what Apply opens)
// and Dismiss (hidden for this run in this browser; "Show dismissed" brings
// them back). Read only: Apply opens an editor, the user saves there.
import { useEffect, useState } from "react";
import { Button, Empty } from "../ui";
import { dismiss, keyOf, loadCoach, restoreAll, useCoach } from "./store";
import { KIND_LABEL, KIND_ORDER, type CoachRunKind, type Suggestion } from "./types";

const NONE: string[] = [];

export type ApplyFn = (s: Suggestion, run: string) => void;

function applyTitle(s: Suggestion): string {
  const a = s.apply;
  if (!a) return "";
  const value = Array.isArray(a.value) ? a.value.join(", ") : String(a.value);
  if (a.target === "bio") return `Opens bio ${a.name} in Roles with ${a.field} = ${value} filled in; Save there keeps it`;
  if (a.target === "lineup") return `Opens the Lineup tab in Roles: ${a.field} = ${value}`;
  return `Opens the plan editor on this run with ${a.field} = ${value} staged`;
}

function Card({ s, run, kind, onApply }: { s: Suggestion; run: string; kind: CoachRunKind; onApply?: ApplyFn }) {
  const where = s.lane_or_part === null || s.lane_or_part === "" ? "" : kind === "mission" ? `part ${s.lane_or_part}`
    : kind === "orchestra" ? `lane ${s.lane_or_part}` : `${kind === "team" ? "stage" : "step"} ${s.lane_or_part}`;
  return (
    <article className="cc-card" data-testid="coach-card" data-id={s.id} data-kind={s.kind} data-severity={s.severity}>
      <header className="cc-card-head">
        <span className="og-chip mono cc-sev" data-severity={s.severity}>{s.severity}</span>
        {where && <span className="mono muted cc-where">{where}</span>}
        {s.bio && <span className="og-chip mono cc-bio" title="the bio this lane ran as">{s.bio}</span>}
      </header>
      <p className="cc-text">{s.text}</p>
      <ul className="cc-why mono" data-testid="coach-why" aria-label="Why">
        {s.why.map((w, i) => <li key={i}>{w}</li>)}
      </ul>
      <div className="cc-actions">
        {s.apply && onApply && (
          <Button size="sm" variant="primary" onClick={() => onApply(s, run)} title={applyTitle(s)} data-testid="coach-apply">Apply</Button>
        )}
        {s.apply && !onApply && <span className="muted cc-hint">change: {s.apply.field}</span>}
        <span className="spacer" />
        <Button size="sm" variant="ghost" onClick={() => dismiss(kind, run, s.id)} title="Hide this card for this run" data-testid="coach-dismiss">Dismiss</Button>
      </div>
    </article>
  );
}

export function CoachCards({ kind, run, onApply }: { kind: CoachRunKind; run: string; onApply?: ApplyFn }) {
  useEffect(() => void loadCoach(kind, run), [kind, run]);
  const entry = useCoach((s) => s.runs[keyOf(kind, run)]);
  const hidden = useCoach((s) => s.dismissed[keyOf(kind, run)] || NONE);
  const [showAll, setShowAll] = useState(false);
  if (!entry || (entry.loading && !entry.result)) return <div className="og-wait mono muted">reading the run's files...</div>;
  if (!entry.result) return <Empty title="Studio could not read the coach" body={entry.error} />;
  const all = entry.result.suggestions;
  const shown = showAll ? all : all.filter((s) => !hidden.includes(s.id));
  const nHidden = all.length - all.filter((s) => !hidden.includes(s.id)).length;
  return (
    <div className="cc" data-testid="coach" data-run={run} data-kind={kind}>
      <div className="cc-head mono muted">
        <span>{all.length ? `${all.length} suggestion${all.length === 1 ? "" : "s"} from the run's files` : "nothing to suggest"}</span>
        <span className="spacer" />
        {nHidden > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setShowAll((v) => !v)} data-testid="coach-show-dismissed">
            {showAll ? "Hide dismissed" : `Show dismissed (${nHidden})`}
          </Button>
        )}
        {showAll && nHidden > 0 && <Button size="sm" variant="ghost" onClick={() => restoreAll(kind, run)}>Restore all</Button>}
      </div>
      {!all.length && <Empty title="Nothing to coach" body="The run's files show no lane sent back twice, no denied tool, no long wait and no gate that looped." testid="coach-empty" />}
      {KIND_ORDER.map((k) => {
        const rows = shown.filter((s) => s.kind === k);
        if (!rows.length) return null;
        return (
          <section key={k} className="cc-group" data-kind={k}>
            <div className="rail-label mono">{KIND_LABEL[k]} · {rows.length}</div>
            {rows.map((s) => <Card key={s.id} s={s} run={run} kind={kind} onApply={onApply} />)}
          </section>
        );
      })}
    </div>
  );
}
