// 3.3.7.0 R2: on the machine that runs `halo host`, the requests its peers queued for the owner under
// fleet.allow_control: ask (GET local/host-pending, studio/local_host_api.py): who asks, for which operation, how
// long the row lives, with Allow and Deny (POST local/host-pending/<id>/allow | deny). An allowed operation runs once
// when the peer sends it again within the row's time; an allowed grant request adds the grant. Nothing shows when
// nothing waits.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../../lib/ui";
import { act, useLocal } from "./store";
import type { PendingRow } from "./types";

const POLL_MS = 15_000;

function what(r: PendingRow): string {
  const ps = Object.entries(r.params || {}).map(([k, v]) => `${k} ${String(v)}`).join(", ");
  return r.kind === "grant" ? `the ${r.grant} grant` : `${r.op}${ps ? ` (${ps})` : ""}`;
}

export function HostPending() {
  const [rows, setRows] = useState<PendingRow[]>([]);
  const busy = useLocal((s) => !!s.busy);
  const said = useLocal((s) => s.said["pending"]);
  const load = async () => {
    try {
      const r = await api.get<{ pending: PendingRow[] }>("local/host-pending");
      setRows(r.pending || []);
    } catch {
      setRows([]);
    }
  };
  useEffect(() => {
    void load();
    const id = window.setInterval(() => {
      if (!document.hidden) void load();
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, []);
  const answer = async (id: string, allow: boolean) => {
    await act("pending", `local/host-pending/${encodeURIComponent(id)}/${allow ? "allow" : "deny"}`, {});
    void load();
  };
  if (!rows.length && !said) return null;
  const now = Date.now() / 1000;
  return (
    <section className="lc-block" aria-label="ASKED OF THIS HOST" data-testid="local-host-pending">
      <div className="rail-label mono">ASKED OF THIS HOST · FLEET.ALLOW_CONTROL: ASK</div>
      <ul className="lc-loaded">
        {rows.map((r) => (
          <li key={r.id} data-testid="local-host-pending-row" data-id={r.id} data-state={r.state}>
            <span className="mono">{r.peer} asks: {what(r)}</span>
            <span className="muted">{r.state === "allowed" ? "allowed, waiting for it to be sent again" : `${Math.max(0, Math.round(r.expires - now))} s left`}</span>
            <span className="spacer" />
            {r.state === "pending" && (
              <>
                <Button size="sm" variant="primary" disabled={busy} onClick={() => void answer(r.id, true)} data-testid="local-host-allow"
                        title={`halo host allow ${r.id}`}>Allow</Button>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => void answer(r.id, false)} data-testid="local-host-deny"
                        title={`halo host deny ${r.id}`}>Deny</Button>
              </>
            )}
          </li>
        ))}
      </ul>
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="local-host-pending-said">{said.text}</div>}
    </section>
  );
}
