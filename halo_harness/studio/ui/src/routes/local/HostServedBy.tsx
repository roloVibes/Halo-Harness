// 3.3.7.0 R1: a Hosts card's "served by halo host at <addr>" line (studio/local_hosts_view.py `host`,
// ollama_steward/host_reads.host_block): when the host started, when this Studio last heard from it and how many
// requests its audit holds -- or, when it did not answer, why. The card, the log line and the Logs page then read
// through that host (the ladder's host rung). 3.3.7.0 R2: this peer's grants there (studio/local_host_acts.py) --
// with `control` Load, Unload, probe and bench go through the host; without it, "Request control" writes a pending
// row its owner answers (`halo host allow <id>` there, or that machine's Hosts page).
import { Button } from "../../lib/ui";
import { requestControl, useLocal } from "./store";
import type { Controls, HostBlock } from "./types";

function ago(t: number | null | undefined): string {
  if (!t) return "never";
  const s = Math.max(0, Math.round(Date.now() / 1000 - t));
  return s < 120 ? `${s} s ago` : s < 7200 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`;
}

function when(t: number | null | undefined): string {
  return t ? new Date(t * 1000).toLocaleString("en-US", { hour12: false }) : "?";
}

function Grants({ ctl, name }: { ctl: Controls; name: string }) {
  const busy = useLocal((s) => !!s.busy);
  const said = useLocal((s) => s.said[`req|${name}`]);
  if (ctl.via !== "host" || !ctl.grants) return null;
  const how = ctl.cap === "none" ? " -- strictly a monitor there (fleet.allow_control: none)"
    : ctl.asks ? " -- its owner is asked first (fleet.allow_control: ask)" : "";
  return (
    <div className="mono muted lc-host-line" data-testid="local-host-grants" data-grants={ctl.grants.join(",")}
         title="this peer's grants on that halo host (halo host grant there gives one)">
      grants there: {ctl.grants.join(", ")}{how}
      {ctl.request && (
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => void requestControl(name)} data-testid="local-host-request"
                title="writes a pending row on that host; its owner answers it (halo host allow <id> there)">Request control</Button>
      )}
      {said && <span className="lc-said" data-ok={said.ok || undefined} data-testid="local-host-request-said"> {said.text}</span>}
    </div>
  );
}

export function HostServedBy({ b, ctl, name }: { b: HostBlock | null | undefined; ctl?: Controls; name?: string }) {
  if (!b) return null;
  const n = b.audit_count ?? 0;
  const text = b.error
    ? `served by halo host at ${b.addr} -- ${b.error}`
    : `served by halo host at ${b.addr} -- running since ${when(b.started)}, last seen ${ago(b.last_seen)}, ${n} request${n === 1 ? "" : "s"} in its audit`;
  return (
    <>
      <div className="mono muted lc-host-line" data-testid="local-host-host" data-addr={b.addr} data-ok={b.error ? "no" : "yes"}
           title={`paired with halo host join (${b.url}); its card, log and profiles are read through it`}>
        {text}
      </div>
      {ctl && name ? <Grants ctl={ctl} name={name} /> : null}
    </>
  );
}
