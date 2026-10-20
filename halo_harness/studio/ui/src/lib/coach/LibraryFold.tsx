// The coach's improvement library on the Coach tab (3.1.6.0 R3;
// halo_harness/orchestra/coach_library.py): the one line the CLI prints too
// ("the library: 3 earlier runs like this adopted ..."), then a "Library (n)"
// fold under the header row listing the entries the coach cites for this run
// (title, when, project), each with Forget (a confirm first; the entry's
// folder is deleted, nothing else changes). Every Apply makes an entry; the
// next run still starts from the base lineup.
import { useState } from "react";
import { Button } from "../ui";
import { forgetEntry } from "./actions";
import { keyOf, useCoach } from "./store";
import type { CoachRunKind, LibraryEntry } from "./types";

const NONE: LibraryEntry[] = [];

function Row({ e, kind, run }: { e: LibraryEntry; kind: CoachRunKind; run: string }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const project = `${e.project?.name || "-"}${e.project?.remote ? ` (${e.project.remote})` : ""}`;
  return (
    <li className="cc-lib-row" data-testid="coach-library-row" data-entry={e.entry}>
      <div className="cc-lib-main">
        <span className="cc-lib-title">{e.title}</span>
        <span className="mono muted cc-lib-meta">
          {e.entry} · {e.when} · {project}{e.same_project ? "" : " · like this goal"}{e.from ? ` · from ${e.from}` : ""}
        </span>
      </div>
      {!asking && (
        <Button size="sm" variant="ghost" onClick={() => setAsking(true)} data-testid="coach-library-forget"
                title="Delete this library entry (asks first); the files it wrote stay as they are">Forget</Button>
      )}
      {asking && (
        <span className="cc-lib-confirm" data-testid="coach-library-confirm" role="group" aria-label={`Forget ${e.entry}`}>
          <span className="muted cc-hint">Forget {e.entry}? Its folder is deleted.</span>
          <Button size="sm" variant="ghost" onClick={() => setAsking(false)} data-testid="coach-library-forget-cancel"
                  title="Keep the entry">Cancel</Button>
          <Button size="sm" variant="danger" disabled={busy} data-testid="coach-library-forget-yes"
                  title="Delete the entry's folder now"
                  onClick={() => { setBusy(true); void forgetEntry(kind, run, e.entry).finally(() => setBusy(false)); }}>Forget</Button>
        </span>
      )}
    </li>
  );
}

export function LibraryFold({ kind, run }: { kind: CoachRunKind; run: string }) {
  const result = useCoach((s) => s.runs[keyOf(kind, run)]?.result);
  const rows = result?.library || NONE;
  if (!rows.length) return null;
  return (
    <div className="cc-lib" data-testid="coach-library-block">
      {result?.library_line && <p className="cc-lib-line mono" data-testid="coach-library-line">{result.library_line}</p>}
      <details className="cc-lib-fold" data-testid="coach-library">
        <summary className="mono" data-testid="coach-library-summary"
                 title="The coach's improvement library: entries earlier Applies made, cited here because their project or goal is like this run's. Nothing is inherited; each change is still a card you Apply.">
          Library ({rows.length})
        </summary>
        <ul className="cc-lib-list">
          {rows.map((e) => <Row key={e.entry} e={e} kind={kind} run={run} />)}
        </ul>
      </details>
    </div>
  );
}
