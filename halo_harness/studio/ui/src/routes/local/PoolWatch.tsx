// Local -> Pool, measured and watched (3.3.8.0 R4; studio/pool_watch_api.py; docs/STUDIO-local-pool.md "The speed card
// and the findings"): the Bench block -- its cost line first (seconds, and that the members' GPUs are busy for them),
// Bench / Quick bench (the 3.3.6.0 battery against the running pool: the measured tok/s and TTFT per window, the cold
// load), the pool's speed card and the penalty line ("pool: 11.2 tok/s measured, -38 % vs pc alone"; "extrapolated"
// until a card exists), the bundles that hold the pool -- and the Findings block: the steward's pool-degraded,
// pool-rtt and pool-spill, one line each, keyed pool|<model>. Nothing runs until Bench is pressed.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { benchNow, BUSY_MS, loadBench, loadFindings, usePoolWatch, WATCH_MS } from "./poolwatchstore";

export function PoolBench() {
  const b = usePoolWatch((s) => s.bench);
  const busy = usePoolWatch((s) => s.busy);
  const said = usePoolWatch((s) => s.said);
  const running = !!b?.bench?.busy;
  useEffect(() => {
    void loadBench();
    const id = window.setInterval(() => {
      if (!document.hidden) void loadBench();
    }, running ? BUSY_MS : WATCH_MS);
    return () => window.clearInterval(id);
  }, [running]);
  const est = b?.estimate;
  const off = !est || running || busy;
  return (
    <section className="pool-block" data-testid="pool-bench" data-measured={b?.speed?.measured || undefined}
             aria-label="Bench">
      <div className="rail-label mono">BENCH · THE POOL'S SPEED CARD</div>
      <p className="mono muted" data-testid="pool-bench-cost">
        {est ? est.line : "the pool is not running: Warm it, then Bench measures it"}
      </p>
      <div className="pool-scan-row">
        <Button variant="primary" size="sm" disabled={off} onClick={() => void benchNow(false)} data-testid="pool-bench-run"
                title={`${b?.cli || "halo local bench --host pool"}: the battery at each window, then the reply reserve`}>
          {running ? "Benching..." : "Bench"}
        </Button>
        <Button size="sm" disabled={off} onClick={() => void benchNow(true)} data-testid="pool-bench-quick"
                title={`${b?.cli || "halo local bench --host pool"} --quick: the pool's -c alone`}>Quick bench</Button>
      </div>
      {b?.speed && (
        <p className="mono pool-penalty" data-testid="pool-bench-penalty" data-measured={b.speed.measured || undefined}
           title={b.speed.penalty_from}>pool: {b.speed.word}</p>
      )}
      {b?.card && (
        <ul className="pool-card-lines mono" data-testid="pool-bench-card" data-model={b.card.model}>
          {b.card.lines.map((l, i) => <li key={`${i}|${l}`}>{l}</li>)}
        </ul>
      )}
      {(b?.bench?.lines?.length || 0) > 0 && (
        <ul className="pool-warm-lines mono" data-testid="pool-bench-lines"
            data-ok={b?.bench.ok ? "1" : b?.bench.ok === false ? "0" : undefined}>
          {(b?.bench.lines || []).map((l, i) => <li key={`${i}|${l}`}>{l}</li>)}
        </ul>
      )}
      {b?.bench?.say && <p className="mono lc-said" data-testid="pool-bench-say">{b.bench.say}</p>}
      {(b?.held?.length || 0) > 0 && (
        <p className="mono muted" data-testid="pool-held">
          {(b?.held || []).map((h) => `${h.bundle} holds the pool for ${h.model} (priority ${h.priority || "normal"}`
            + (h.hours ? `, ${h.hours}` : "") + ")").join(" · ")}
        </p>
      )}
      {said && !said.ok && <p className="mono lc-said" data-testid="pool-bench-said">{said.text}</p>}
    </section>
  );
}

export function PoolFindings() {
  const rows = usePoolWatch((s) => s.findings);
  useEffect(() => {
    void loadFindings();
    const id = window.setInterval(() => {
      if (!document.hidden) void loadFindings();
    }, WATCH_MS);
    return () => window.clearInterval(id);
  }, []);
  return (
    <section className="pool-block" data-testid="pool-findings" data-count={rows ? rows.length : undefined}
             aria-label="Findings">
      <div className="rail-label mono">FINDINGS · THE STEWARD WATCHES THE POOL</div>
      {!rows && <p className="mono muted">reading the steward's findings...</p>}
      {rows && !rows.length && (
        <p className="mono muted" data-testid="pool-findings-none">no pool finding: the controller's log shows no lost RPC
          backend, no node below its split and no reply slower than the link explains</p>
      )}
      <ul className="pool-run-members">
        {(rows || []).map((f) => (
          <li key={f.id} className="pool-finding mono" data-testid="pool-finding" data-rule={f.rule} data-severity={f.severity}>
            <span className="og-chip mono">{f.rule}</span> {f.finding}
          </li>
        ))}
      </ul>
    </section>
  );
}
