// Benchmarks, block two (3.3.6.0 R5; ollama_steward/tune_report.py): the tuning report for one host -- the warm set
// that fits together and what a pivot to each other model costs, each model's window alone / beside the warm set /
// with a q8_0 KV cache, the reserve each needs, the findings the steward's rules raise here -- and every option as a
// line that says what it does, what it writes and how long it takes. A Halo-side option has Apply with its scope
// (keep preselected); a server-side one shows the exact line for that host's shell and the line that reverts it, for
// you to run (Halo never runs them).
import { useEffect, useState } from "react";
import { Button } from "../../lib/ui";
import { ScopePick } from "../shared/ScopePick";
import { applyOption, loadTune, useBench, type Scope, type TuneOption } from "./benchstore";

function Server({ o }: { o: TuneOption }) {
  return (
    <ul className="tune-server mono" data-testid="tune-server">
      {Object.entries(o.server || {}).map(([os, s]) => (
        <li key={os} data-os={os}>
          <span className="muted">{os === "any" ? "run" : os}:</span> <code data-testid="tune-set">{s.set}</code>
          <div className="muted">revert: <code data-testid="tune-revert">{s.revert}</code>{s.restart !== "no restart" ? ` · then ${s.restart}` : ""}</div>
        </li>
      ))}
    </ul>
  );
}

function Option({ host, o }: { host: string; o: TuneOption }) {
  const [scope, setScope] = useState<Scope>(o.scope_default || "keep");
  const said = useBench((s) => s.said[`opt|${o.id}`]);
  return (
    <li className="tune-opt" data-testid="tune-option" data-kind={o.kind} data-id={o.id}>
      <div className="tune-line"><span className="og-chip mono" data-kind={o.kind}>{o.kind === "halo" ? "Halo" : "server"}</span> {o.line}</div>
      <div className="mono muted tune-meta">writes {o.writes} · takes {o.takes}</div>
      {o.kind === "halo" ? (
        <div className="tune-apply">
          <ScopePick value={scope} onChange={setScope} name={`scope-${o.id}`} testid="tune-scope" />
          <Button size="sm" onClick={() => void applyOption(host, o.id, scope)} data-testid="tune-apply"
                  title={`halo local tune --host ${host} --apply ${o.id} --scope ${scope}`}>Apply</Button>
        </div>
      ) : <Server o={o} />}
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="tune-said">{said.text}</div>}
    </li>
  );
}

export function TuneReport() {
  const hosts = useBench((s) => s.hosts);
  const [host, setHost] = useState("");
  const name = host || hosts?.[0]?.name || "";
  const r = useBench((s) => (name ? s.reports[name] : undefined));
  const said = useBench((s) => s.said[`tune|${name}`]);
  useEffect(() => {
    if (name) {
      void loadTune(name);
    }
  }, [name]);
  if (!name) return null;
  return (
    <div className="tune-report" data-testid="tune-report" data-host={name}>
      {(hosts?.length || 0) > 1 && (
        <label className="mono">host{" "}
          <select className="st-select mono" value={name} onChange={(e) => setHost(e.target.value)} data-testid="tune-host">
            {hosts!.map((h) => <option key={h.name} value={h.name}>{h.name}</option>)}
          </select>
        </label>
      )}
      {said && !said.ok && <p className="mono lc-said">{said.text}</p>}
      {!r ? <p className="mono muted">reading the report...</p> : (
        <>
          <p className="mono" data-testid="tune-says">{r.says}</p>
          {r.warm_set && (
            <div className="mono tune-warm" data-testid="tune-warm">warm set: {r.warm_set.line}
              {r.warm_set.pivots.map((p) => <div key={p.line} className="muted">{p.line}</div>)}
            </div>
          )}
          <ul className="mono tune-models">{r.models.map((m) => <li key={m.model} data-testid="tune-model">{m.line}</li>)}</ul>
          {r.findings.length > 0 && (
            <ul className="mono tune-findings">{r.findings.map((f) => <li key={f.id} data-severity={f.severity} data-testid="tune-finding">{f.line}</li>)}</ul>
          )}
          <ol className="tune-options">{r.options.map((o) => <Option key={o.id} host={name} o={o} />)}</ol>
          <p className="mono muted">the same from a terminal: <code>{r.cli}</code></p>
        </>
      )}
    </div>
  );
}
