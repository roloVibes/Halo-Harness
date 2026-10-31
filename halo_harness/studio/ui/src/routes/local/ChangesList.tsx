// The changes Halo made to local models' profiles, each with its scope (3.3.6.0 R5; ollama_steward/changes.py): who
// made it (the steward, the ledger's dialect refinements, you, the bench), what it changed from and to, its scope
// (keep / until halo exits / until the session ends -- a new pick changes it), and Revert, whose answer says what it
// put back. Benchmarks' third block and Settings -> Local both show it.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { ScopePick } from "../shared/ScopePick";
import { loadChanges, rescope, revertChange, useBench, type Change } from "./benchstore";

function Row({ c }: { c: Change }) {
  const said = useBench((s) => s.said[`chg|${c.id}`]);
  return (
    <li className="chg-row" data-testid="change-row" data-id={c.id} data-scope={c.scope} data-by={c.by}>
      <div className="mono chg-line" data-testid="change-line">{c.line}</div>
      <div className="chg-acts">
        <ScopePick value={c.scope} onChange={(s) => void rescope(c.id, s)} name={`chg-${c.id}`} testid="change-scope" />
        <Button size="sm" variant="ghost" onClick={() => void revertChange(c.id)} data-testid="change-revert"
                title={`halo local revert ${c.id}`}>Revert</Button>
      </div>
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="change-said">{said.text}</div>}
    </li>
  );
}

export function ChangesList({ host }: { host?: string }) {
  const all = useBench((s) => s.changes);
  const said = useBench((s) => s.said["chg|last"]);
  useEffect(() => {
    void loadChanges();
  }, []);
  if (!all) return <p className="mono muted">reading the changes...</p>;
  const rows = host ? all.filter((c) => c.host === host) : all;
  return (
    <div className="chg-list" data-testid="changes-list">
      {rows.length ? (
        <>
          <ul>{rows.map((c) => <Row key={c.id} c={c} />)}</ul>
          <Button size="sm" variant="ghost" onClick={() => void revertChange("all")} data-testid="change-revert-all" title="halo local revert --all">
            Revert all
          </Button>
        </>
      ) : <p className="mono muted" data-testid="changes-none">No change Halo made to a local model is in force.</p>}
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="change-reverted">{said.text}</div>}
    </div>
  );
}
