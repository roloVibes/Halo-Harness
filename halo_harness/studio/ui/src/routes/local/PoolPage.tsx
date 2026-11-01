// Local -> Pool (3.3.8.0 R1 + R3; docs/POOL.md): several paired hosts' GPU memory serving one model over llama.cpp RPC.
// The members (PoolMembers.tsx: host, GPU, free / total VRAM, link, RTT, the split), Warm and Stop (PoolRun.tsx: the
// preflight's checks, Warm only when they are green, the running pool's state and claims), Scan (the RPC port on this
// machine's /24 and on every member -- only when pressed, never on a page load) with Add on each new responder, and
// what the pool can run (PoolRecommend.tsx: the fit and the preview before any download). The page reads the members
// and the recommendation on open and every 30 s while it is open (poolstore.ts), the run every 10 s (poolrunstore.ts).
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { HfCards } from "./HfCards";
import { PoolMembers } from "./PoolMembers";
import { PoolRecommend } from "./PoolRecommend";
import { PoolRun } from "./PoolRun";
import { addMember, loadPool, nameFor, REFRESH_MS, scanNow, usePool, type Probe } from "./poolstore";

function Candidate({ c }: { c: Probe }) {
  const key = `add|${c.host}:${c.port}`;
  const busy = usePool((s) => s.busy === key);
  const said = usePool((s) => s.said[key]);
  const taken = usePool((s) => !!c.paired && !!s.members?.members.some((m) => m.host === c.paired)); // its card counts once
  const host = c.paired && !taken ? c.paired : c.host;
  const name = nameFor(c, !taken);
  return (
    <li className="pool-cand mono" data-testid="pool-scan-candidate" data-host={c.host} data-alive={c.alive || undefined}
        data-wifi={c.wifi_suspect || undefined} data-member={c.member || undefined}>
      <span>{c.line}</span>
      {c.paired && <span className="og-chip mono">paired host {c.paired}</span>}
      {c.member ? <span className="og-chip mono" data-testid="pool-scan-member">member {c.member}</span> : c.alive && (
        <Button size="sm" disabled={busy} onClick={() => void addMember(name, host, c.port)} data-testid="pool-scan-add"
                title={`halo pool add ${name} ${host}:${c.port}`}>Add as {name}</Button>
      )}
      {said && <span className="mono lc-said" data-ok={said.ok || undefined} data-testid="pool-scan-add-said">{said.text}</span>}
    </li>
  );
}

function ScanBlock() {
  const scan = usePool((s) => s.scan);
  const busy = usePool((s) => s.busy === "scan");
  const said = usePool((s) => s.said.scan);
  const port = usePool((s) => s.members?.rpc_port ?? 50052);
  const last = usePool((s) => s.members?.scan?.line || "");
  return (
    <section className="pool-block" data-testid="pool-scan-block" aria-label="Scan">
      <div className="rail-label mono">SCAN · THE RPC PORT :{port}</div>
      <div className="pool-scan-row">
        <Button variant="primary" size="sm" disabled={busy} onClick={() => void scanNow()} data-testid="pool-scan"
                title={`halo pool scan: a TCP connect on :${port} to every address of this machine's /24 (and pool.scan_subnets) `
                  + "and to every member, about 10 s; it says a port is open and how far away the machine is, not what answers"}>
          {busy ? "Scanning..." : "Scan"}
        </Button>
        <span className="mono muted" data-testid="pool-scan-line">{scan ? scan.line : last ? `last scan: ${last}` : "not scanned yet: Scan asks only when pressed"}</span>
      </div>
      {said && !said.ok && <p className="mono lc-said" data-testid="pool-scan-said">{said.text}</p>}
      {scan && (
        <>
          <ul className="pool-cands" data-testid="pool-scan-candidates" data-count={scan.candidates.length}>
            {scan.candidates.map((c) => <Candidate key={`${c.host}:${c.port}`} c={c} />)}
          </ul>
          {scan.notes.map((n) => <p key={n} className="mono muted" data-testid="pool-scan-note">{n}</p>)}
        </>
      )}
    </section>
  );
}

export function PoolPage() {
  const error = usePool((s) => s.error);
  useEffect(() => {
    loadPool();
    const id = window.setInterval(() => {
      if (!document.hidden) loadPool();
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className="lc-pool" data-testid="local-pool">
      <p className="mono pool-note" data-testid="pool-note">
        Pooling adds capacity, not speed: measured 21-55 % slower than one node that holds the model. rpc-server has no
        authentication -- a trusted LAN only; the pool's llama-server listens on this machine's LAN address behind a
        generated key.
      </p>
      {error && <p className="mono lc-said" data-testid="pool-error">{error}</p>}
      <PoolMembers />
      <PoolRun />
      <ScanBlock />
      <PoolRecommend />
      <HfCards />
    </div>
  );
}
