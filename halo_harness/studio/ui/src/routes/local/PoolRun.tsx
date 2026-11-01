// Local -> Pool, Warm and Stop (3.3.8.0 R3; studio/pool_act_api.py; docs/STUDIO-local-pool.md "Warm and Stop"): the
// model the pool would run (what fits it, from the recommendation), the Wi-Fi switch (a Wi-Fi member is left out
// unless it is on), the preflight's checks one row each -- Warm is enabled only when every one is green -- and the
// running pool: its state (running / loading / degraded (worker2 down) / down), each member's claim and its lease,
// the lines of the last Warm, the 10 min cooldown, Stop. Warm is one change under the steward contract: the claims on
// every member (the models resident there pivoted out first, said), each worker's rpc-server, then llama-server.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { usePool } from "./poolstore";
import { BUSY_MS, loadPreflight, loadRun, pickModel, RUN_MS, setWifi, stopNow, usePoolRun, warmNow,
  type Check, type RunMember } from "./poolrunstore";

function CheckRow({ c }: { c: Check }) {
  return (
    <li className="pool-check mono" data-testid="pool-preflight-check" data-check={c.check} data-ok={c.ok || undefined}>
      <span className="pool-check-mark" data-ok={c.ok || undefined}>{c.ok ? "ok" : "blocks"}</span>
      <b>{c.check}</b> {c.lines.join(" · ")}
    </li>
  );
}

function MemberRow({ m }: { m: RunMember }) {
  const up = m.alive === null ? "this GPU" : m.alive ? "up" : "down";
  return (
    <li className="pool-run-member mono" data-testid="pool-run-member" data-name={m.name} data-up={up}
        data-live={m.claim.live === null ? undefined : String(m.claim.live)}>
      <b>{m.name}</b> {up}{m.addr ? ` (${m.addr})` : ""} -- {m.claim.line}
    </li>
  );
}

function Preflight() {
  const pf = usePoolRun((s) => s.pf);
  const said = usePoolRun((s) => s.said.preflight);
  if (!pf) return <p className="mono muted" data-testid="pool-preflight-reading">{said ? said.text : "reading the preflight..."}</p>;
  return (
    <div className="pool-preflight" data-testid="pool-preflight" data-ok={pf.ok || undefined} data-model={pf.model}>
      <p className="mono" data-testid="pool-preflight-line">{pf.line}</p>
      <ul className="pool-checks">{pf.checks.map((c) => <CheckRow key={c.check} c={c} />)}</ul>
    </div>
  );
}

export function PoolRun() {
  const rows = usePool((s) => s.rec?.rows);
  const run = usePoolRun((s) => s.run);
  const model = usePoolRun((s) => s.model);
  const wifi = usePoolRun((s) => s.wifi);
  const pf = usePoolRun((s) => s.pf);
  const busy = usePoolRun((s) => s.busy);
  const said = usePoolRun((s) => s.said.warm || s.said.stop);
  const warming = !!run?.warm?.busy;
  const candidates = (rows || []).filter((v) => v.state === "pool");
  const first = candidates.length ? candidates[0].model : "";
  useEffect(() => {
    if (!model && first) pickModel(first);
  }, [model, first]);
  useEffect(() => {
    void loadRun();
    const id = window.setInterval(() => {
      if (!document.hidden) void loadRun();
    }, warming ? BUSY_MS : RUN_MS);
    return () => window.clearInterval(id);
  }, [warming]);
  useEffect(() => {
    if (!warming && run?.warm?.ok !== undefined) void loadPreflight();
  }, [warming, run?.warm?.ok]);
  const state = run?.state || "stopped";
  const on = state !== "stopped";
  const canWarm = !!pf?.ok && !on && !warming && !busy && !run?.cooldown;
  const why = !pf ? "the preflight has not answered yet" : !pf.ok ? pf.line : on ? "the pool runs already: Stop it first"
    : run?.cooldown || "";
  return (
    <section className="pool-block" data-testid="pool-run" data-state={state} aria-label="Warm and Stop">
      <div className="rail-label mono">RUN · WARM AND STOP</div>
      <p className="mono pool-run-state" data-testid="pool-run-state" data-state={state}>{run ? run.line : "reading the pool..."}</p>
      {on && run && (
        <ul className="pool-run-members" data-testid="pool-run-members">{run.members.map((m) => <MemberRow key={m.name} m={m} />)}</ul>
      )}
      <div className="pool-scan-row">
        <label className="mono muted">model{" "}
          <select value={model} onChange={(e) => pickModel(e.target.value)} data-testid="pool-run-model" disabled={on}>
            {!candidates.length && <option value="">nothing fits the pool</option>}
            {candidates.map((v) => <option key={v.model} value={v.model}>{v.display}</option>)}
          </select>
        </label>
        <label className="mono muted" title="a Wi-Fi member waits a round trip per layer boundary: left out unless this is on">
          <input type="checkbox" checked={wifi} onChange={(e) => setWifi(e.target.checked)} data-testid="pool-run-wifi" disabled={on} />
          {" "}keep a Wi-Fi member (a slower decode)
        </label>
        <Button variant="primary" size="sm" disabled={!canWarm} onClick={() => void warmNow()} data-testid="pool-warm"
                title={canWarm ? `${pf?.cli.replace("halo pool preflight", "halo local serve --pool")}: the claims, the rpc-servers, then llama-server -- one change, one per 10 min`
                  : why}>
          {warming ? "Warming..." : "Warm"}
        </Button>
        <Button size="sm" disabled={!on || busy === "stop"} onClick={() => void stopNow()} data-testid="pool-stop"
                title="halo pool stop: llama-server stopped, the claims released, the models it pivoted out back (said)">Stop</Button>
      </div>
      {run?.cooldown && <p className="mono muted" data-testid="pool-run-cooldown">{run.cooldown}</p>}
      {!on && <Preflight />}
      {run?.warm?.lines && run.warm.lines.length > 0 && (
        <ul className="pool-warm-lines mono" data-testid="pool-warm-lines" data-ok={run.warm.ok ? "1" : run.warm.ok === false ? "0" : undefined}>
          {run.warm.lines.map((l, i) => <li key={`${i}|${l}`}>{l}</li>)}
        </ul>
      )}
      {said && !said.ok && <p className="mono lc-said" data-testid="pool-run-said">{said.text}</p>}
    </section>
  );
}
