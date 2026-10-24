// The Report panel's Artifacts tab (3.2.0.0 R5): a workflow run's typed
// outputs (report.json `artifacts`, halo_harness/workflows/outputs.py), each
// read through GET orchestra/<run>/artifact/<name> and drawn by its schema's
// view hint (packs/ArtifactView.tsx). A skipped or missing output says why.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Empty } from "../../lib/ui";
import { ArtifactProblems, ArtifactView, type ArtifactPayload } from "../packs/ArtifactView";
import { useOrch } from "./store";
import type { ArtifactRow } from "./types";

function One({ run, row }: { run: string; row: ArtifactRow }) {
  const [a, setA] = useState<ArtifactPayload | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    if (row.state !== "saved") return;
    api.get<ArtifactPayload>(`orchestra/${run}/artifact/${row.name}`).then(
      (got) => live && setA(got),
      (e) => live && setError(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      live = false;
    };
  }, [run, row.name, row.state, row.path]);
  return (
    <section className="og-artifact" data-testid="run-artifact" data-name={row.name} data-state={row.state} data-ok={String(row.ok !== false)}>
      <div className="og-artifact-head">
        <strong>{row.name}</strong>
        <span className="mono muted">
          {row.schema || row.type} · {row.view} · {row.state}
          {row.lane ? ` · lane ${row.lane}` : ""}
        </span>
      </div>
      {row.why && <p className="muted">{row.why}</p>}
      <ArtifactProblems list={row.problems || []} />
      {error && <div className="field-error">{error}</div>}
      {a && <ArtifactView doc={a.data} view={a.view} columns={a.columns} />}
    </section>
  );
}

export function ArtifactsTab() {
  const runId = useOrch((s) => s.runId);
  const rows = useOrch((s) => s.data?.report?.artifacts) || [];
  const ref = useOrch((s) => s.data?.report?.workflow?.ref);
  if (!rows.length) return <Empty title="No artifacts" body="This run's workflow names no typed output." />;
  return (
    <div className="og-artifacts" data-testid="run-artifacts">
      {ref && <div className="mono muted">workflow {ref}</div>}
      {rows.map((r) => (
        <One key={`${r.name}-${r.lane || 0}`} run={runId} row={r} />
      ))}
    </div>
  );
}
