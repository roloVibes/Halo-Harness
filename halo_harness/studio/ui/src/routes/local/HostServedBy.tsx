// 3.3.7.0 R1: a Hosts card's "served by halo host at <addr>" line (studio/local_hosts_view.py `host`,
// ollama_steward/host_reads.host_block): when the host started, when this Studio last heard from it and how many
// requests its audit holds -- or, when it did not answer, why. The card, the log line and the Logs page then read
// through that host (the ladder's host rung); Load and Unload through it wait for the `control` grant (3.3.7.0 R2).
import type { HostBlock } from "./types";

function ago(t: number | null | undefined): string {
  if (!t) return "never";
  const s = Math.max(0, Math.round(Date.now() / 1000 - t));
  return s < 120 ? `${s} s ago` : s < 7200 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`;
}

function when(t: number | null | undefined): string {
  return t ? new Date(t * 1000).toLocaleString("en-US", { hour12: false }) : "?";
}

export function HostServedBy({ b }: { b: HostBlock | null | undefined }) {
  if (!b) return null;
  const n = b.audit_count ?? 0;
  const text = b.error
    ? `served by halo host at ${b.addr} -- ${b.error}`
    : `served by halo host at ${b.addr} -- running since ${when(b.started)}, last seen ${ago(b.last_seen)}, ${n} request${n === 1 ? "" : "s"} in its audit`;
  return (
    <div className="mono muted lc-host-line" data-testid="local-host-host" data-addr={b.addr} data-ok={b.error ? "no" : "yes"}
         title={`paired with halo host join (${b.url}); its card, log and profiles are read through it`}>
      {text}
    </div>
  );
}
